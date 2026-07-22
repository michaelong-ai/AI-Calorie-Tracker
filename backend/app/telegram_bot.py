"""Telegram bot — log meals from your phone, anywhere (T6.2 + T6.3, idea E3).

WHY THIS EXISTS
    You are out eating; your phone is in your hand with Telegram already open.
    Sending a photo to a bot is less friction than opening the web app. This
    module lets you do exactly that: photo/text in a chat -> the SAME AI
    estimation the web wizard uses -> a reply you confirm with a tap -> the
    entry lands in your tracker through the SAME write path as everything else.

WHY LONG POLLING (not a webhook)
    A webhook needs Telegram to call US, which needs a public URL, which needs
    a deploy. Long polling is the reverse: WE repeatedly call Telegram asking
    "any new messages?" — outbound HTTPS only, exactly like a browser fetching
    a page. So this runs on your PC behind your home router with no deploy.
    The trade-off: your PC must be on. (Sprint 7 swaps this for a webhook once
    the app is hosted — a small change, isolated to this file.)

HOW IT RUNS
    A separate process from the web server (start it with dev-bot.ps1), mirror-
    ing the dev-backend / dev-frontend split you already use. It imports and
    calls the backend's own functions directly — estimate_nutrition() for the
    AI, and create_entry() for saving — so there is still ONE estimation
    codepath and ONE write path, shared with the web app.

AUTH (the multi-user "empty slot", first real customer)
    The bot answers exactly one person. If TELEGRAM_CHAT_ID is set in .env,
    only that chat is served. If it is NOT set, the first chat to message the
    bot becomes the owner for this run and the bot tells you the id to paste
    into .env to lock it permanently. Every other chat is refused.
"""

import logging
import os
from datetime import date, timedelta
from pathlib import Path

# Trust the OS certificate store for HTTPS BEFORE any HTTPS call is made — the
# same antivirus-interception fix the web server uses (see main.py / README).
# This one process makes HTTPS calls to BOTH Telegram and Anthropic, so it
# needs the fix independently of the web server.
import truststore

truststore.inject_into_ssl()

import httpx
from dotenv import load_dotenv

# Load backend/.env (token, chat id, Anthropic key) before reading any of it.
load_dotenv(Path(__file__).parent.parent / ".env")

from app.logging_config import setup_logging
from app.routers.days import day_summaries
from app.routers.entries import EntryInput, create_entry, list_entries
from app.routers.goals import active_goal
from app.services.estimation import EstimationError, estimate_nutrition

setup_logging()
logger = logging.getLogger(__name__)

# --- Configuration ------------------------------------------------------------

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
# The allowed chat id, if the user has already locked it in .env. Kept as a
# string because Telegram ids arrive as strings in our comparisons.
CONFIGURED_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip() or None

# Telegram's two base URLs: one for API methods, one for downloading files.
API_BASE = f"https://api.telegram.org/bot{TOKEN}"
FILE_BASE = f"https://api.telegram.org/file/bot{TOKEN}"

# How long Telegram holds each getUpdates request open waiting for a message
# (server-side long poll). Our HTTP read timeout must comfortably exceed it.
POLL_TIMEOUT_S = 30

# In-memory store of estimates awaiting a ✅/❌ decision, keyed by a short id
# we put in the button's callback_data (Telegram caps callback_data at 64
# bytes, so we can't stuff the whole estimate in there). Lost on restart —
# fine for a personal bot; a pending estimate just needs re-sending.
_pending: dict[str, dict] = {}
_pending_seq = 0

# The chat we're serving this run. Seeded from .env; learned on first contact
# if .env didn't set it.
_owner_chat_id: str | None = CONFIGURED_CHAT_ID


# --- Telegram API helpers -----------------------------------------------------


def _call(client: httpx.Client, method: str, **params) -> dict:
    """Call one Telegram Bot API method and return its `result`.

    `method` is e.g. "sendMessage"; params are the method's arguments. Raises
    on transport errors (the caller's loop catches and retries).
    """
    resp = client.post(f"{API_BASE}/{method}", json=params)
    resp.raise_for_status()
    body = resp.json()
    if not body.get("ok"):
        # Telegram reported a logical error (bad chat id, etc.) — log and
        # return an empty result so callers degrade instead of crashing.
        logger.warning("Telegram %s failed: %s", method, body.get("description"))
        return {}
    return body.get("result", {})


def _send(client: httpx.Client, chat_id, text: str, buttons: list | None = None) -> None:
    """Send a text message, optionally with an inline-button keyboard."""
    params: dict = {"chat_id": chat_id, "text": text}
    if buttons is not None:
        # inline_keyboard is a list of button ROWS; we use one row.
        params["reply_markup"] = {"inline_keyboard": [buttons]}
    _call(client, "sendMessage", **params)


def _best_effort(client: httpx.Client, method: str, **params) -> None:
    """Make a COSMETIC Telegram call, ignoring any failure.

    Used for the button polish (answering a tap, removing buttons). These can
    legitimately fail — a tap made while the bot was down is older than
    Telegram's ~1 minute callback window and comes back 400 — and such a
    failure must NEVER abort the real work that follows (saving the entry and
    confirming it). Learned the hard way: a stale tap once saved the meal but
    swallowed the "✅ Logged" reply.
    """
    try:
        _call(client, method, **params)
    except Exception as e:  # noqa: BLE001 — cosmetic by definition
        logger.info("Best-effort %s skipped: %s", method, e)


def _download_photo(client: httpx.Client, file_id: str) -> bytes:
    """Fetch a photo's bytes given its Telegram file_id (two-step: getFile
    returns a path, then we download from the file endpoint)."""
    meta = _call(client, "getFile", file_id=file_id)
    file_path = meta["file_path"]
    resp = client.get(f"{FILE_BASE}/{file_path}")
    resp.raise_for_status()
    return resp.content


# --- Authorisation ------------------------------------------------------------


def _authorise(client: httpx.Client, chat_id) -> bool:
    """Decide whether to serve this chat, learning the owner on first contact.

    Returns True if the message should be processed. Side effects: sets the
    run's owner the first time (when .env didn't), and tells strangers no.
    """
    global _owner_chat_id
    cid = str(chat_id)

    if _owner_chat_id is None:
        # Onboarding: the first person to speak becomes the owner for this run.
        _owner_chat_id = cid
        logger.info("Bot owner learned this run: chat_id=%s", cid)
        _send(
            client, chat_id,
            "👋 You're now connected as this bot's owner.\n\n"
            f"To lock this permanently, add this line to backend/.env and "
            f"restart the bot:\nTELEGRAM_CHAT_ID={cid}\n\n"
            "Send /help to see what I can do.",
        )
        return True

    if cid != _owner_chat_id:
        # Anyone who isn't the owner is politely refused (the auth slot doing
        # its job — this bot is single-user like the rest of the app).
        _send(client, chat_id, "Sorry — this is a private tracker bot.")
        logger.info("Refused message from non-owner chat_id=%s", cid)
        return False

    return True


# --- Rendering an estimate ----------------------------------------------------


def _format_estimate(est) -> str:
    """Turn an Estimate into the chat 'card' text (mirrors the web wizard)."""
    header = "🏷️ Read from label" if est.kind == "label" else "🤖 AI estimate"
    lines = [f"{header}: {est.description}", ""]

    # Per-ingredient breakdown (D4) — the auditable itemisation, if present.
    if est.items:
        for item in est.items:
            lines.append(f"• {item.name}: {round(item.calories)} kcal")
        lines.append("")

    # Assumptions — the model's visible working.
    for assumption in est.assumptions:
        lines.append(f"– {assumption}")
    if est.assumptions:
        lines.append("")

    # For label scans, note the basis so you know what the numbers mean.
    if est.kind == "label" and est.label_basis:
        lines.append(f"(values as printed, per {est.label_basis.per})")

    lines.append(
        f"Total: {round(est.calories)} kcal · "
        f"P {round(est.protein_g)} · C {round(est.carbs_g)} · F {round(est.fat_g)}"
    )
    lines.append(f"Confidence: {est.confidence}")
    return "\n".join(lines)


def _running_total_line() -> str:
    """A '1234 / 2190 kcal · 956 left' summary for today, after a save."""
    today = date.today().isoformat()
    consumed = round(sum(e.calories for e in list_entries(today)))
    goal = active_goal(today)
    if goal is None:
        return f"Today so far: {consumed} kcal (no goal set)."
    target = round(goal.calories_target)
    remaining = target - consumed
    if remaining >= 0:
        return f"Today: {consumed} / {target} kcal · {remaining} kcal left."
    return f"Today: {consumed} / {target} kcal · {abs(remaining)} kcal OVER."


# --- Slash commands: "what have I eaten today?" (D8) --------------------------

HELP_TEXT = (
    "🥗 Calorie Tracker bot\n\n"
    "Log a meal:\n"
    "• Send a photo of your food (or a nutrition label)\n"
    "• Or just type what you ate, e.g. 'chicken rice with egg'\n"
    "Then tap ✅ to log it.\n\n"
    "Check your progress:\n"
    "/today — calories + macros so far today\n"
    "/yesterday — the same for yesterday\n"
    "/week — the last 7 days at a glance\n"
    "/help — this message"
)


# What Telegram shows in the bot's "Menu" button and in the autocomplete list
# when you type "/". Registered once at startup via setMyCommands (below) —
# Telegram stores it against the bot, so it persists between restarts.
COMMAND_MENU = [
    {"command": "today", "description": "Calories + macros so far today"},
    {"command": "yesterday", "description": "Yesterday's totals"},
    {"command": "week", "description": "The last 7 days at a glance"},
    {"command": "help", "description": "What this bot can do"},
]


def _register_commands(client: httpx.Client) -> None:
    """Tell Telegram this bot's command list, so users get a menu.

    Purely cosmetic — the bot answers these commands whether or not they're
    registered — but it makes them DISCOVERABLE instead of something you have
    to remember. Note the names carry no leading "/" here; Telegram adds it.
    """
    _call(client, "setMyCommands", commands=COMMAND_MENU)
    logger.info("Registered %d commands with Telegram", len(COMMAND_MENU))


def _display_date(iso: str) -> str:
    """ISO "2026-07-19" -> "19-Jul-2026" — the app-wide display format (D5)."""
    return date.fromisoformat(iso).strftime("%d-%b-%Y")


def _macro_line(label: str, consumed: float, target: float | None, unit: str) -> str:
    """One 'Protein: 88 / 144 g · 56 to go' row.

    `target` is None on days with no goal, in which case only the consumed
    amount is shown — the spec's "show, don't score" rule for ungoverned days.
    """
    if target is None:
        return f"{label}: {round(consumed)}{unit}"
    remaining = round(target) - round(consumed)
    tail = f"{remaining}{unit} to go" if remaining >= 0 else f"{abs(remaining)}{unit} over"
    return f"{label}: {round(consumed)} / {round(target)}{unit} · {tail}"


def _format_day(iso_date: str, heading: str) -> str:
    """The full day report: totals vs targets, then the meals logged.

    Reuses the SAME data the web app shows — list_entries for the meals and
    active_goal for the targets that applied ON that date (goal versioning).
    """
    entries = list_entries(iso_date)
    goal = active_goal(iso_date)

    # Totals summed from the entries themselves, so this can never disagree
    # with the meal list printed underneath it.
    kcal = sum(e.calories for e in entries)
    protein = sum(e.protein_g for e in entries)
    carbs = sum(e.carbs_g for e in entries)
    fat = sum(e.fat_g for e in entries)

    lines = [f"📊 {heading} ({_display_date(iso_date)})", ""]
    lines.append(_macro_line("Calories", kcal, goal.calories_target if goal else None, " kcal"))
    lines.append(_macro_line("Protein", protein, goal.protein_g_target if goal else None, "g"))
    lines.append(_macro_line("Carbs", carbs, goal.carbs_g_target if goal else None, "g"))
    lines.append(_macro_line("Fat", fat, goal.fat_g_target if goal else None, "g"))

    if goal is None:
        lines.append("\n(no goal set for this day — totals only)")

    if entries:
        lines.append("")
        lines.append(f"{len(entries)} item{'s' if len(entries) != 1 else ''} logged:")
        for e in entries:
            # 📷 marks entries that came from a scan rather than manual typing.
            mark = "📷 " if e.source != "manual" else ""
            lines.append(f"• {mark}{e.description} — {round(e.calories)} kcal")
    else:
        lines.append("\nNothing logged yet — send me a meal photo!")

    return "\n".join(lines)


def _format_week() -> str:
    """The last 7 days: one line per day, plus the average over logged days."""
    today = date.today()
    start = today - timedelta(days=6)
    summaries = day_summaries(start=start.isoformat(), end=today.isoformat())

    # day_summaries only returns days that HAVE entries, so index them by date
    # and walk the full 7-day span ourselves — otherwise a skipped day would
    # silently vanish from the list instead of showing as a gap.
    by_date = {d.local_date: d for d in summaries}

    lines = ["📅 Last 7 days", ""]
    for offset in range(6, -1, -1):  # oldest first
        iso = (today - timedelta(days=offset)).isoformat()
        day = by_date.get(iso)
        if day is None:
            lines.append(f"{_display_date(iso)}: — nothing logged")
            continue
        target = f" / {round(day.target.calories_target)}" if day.target else ""
        lines.append(f"{_display_date(iso)}: {round(day.calories)}{target} kcal")

    # Only days with entries count toward the average — a week where you
    # logged 3 days shouldn't look like a starvation week.
    logged = [d for d in summaries if d.entry_count > 0]
    if logged:
        avg = round(sum(d.calories for d in logged) / len(logged))
        lines.append("")
        lines.append(f"Average over {len(logged)} logged day"
                     f"{'s' if len(logged) != 1 else ''}: {avg} kcal")
    return "\n".join(lines)


def _handle_command(client: httpx.Client, chat_id, text: str) -> bool:
    """Handle a /command. Returns True if the text WAS a command.

    Telegram commands can arrive as "/today@MyBotName" in groups, so we strip
    anything after "@" before matching.
    """
    command = text.strip().split()[0].lower().split("@")[0]

    if command in ("/start", "/help"):
        _send(client, chat_id, HELP_TEXT)
    elif command == "/today":
        _send(client, chat_id, _format_day(date.today().isoformat(), "Today"))
    elif command == "/yesterday":
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        _send(client, chat_id, _format_day(yesterday, "Yesterday"))
    elif command == "/week":
        _send(client, chat_id, _format_week())
    else:
        _send(client, chat_id, f"Unknown command {command}.\n\n{HELP_TEXT}")

    logger.info("Handled command %s", command)
    return True


# --- Handling the two kinds of update -----------------------------------------


def _handle_message(client: httpx.Client, message: dict) -> None:
    """A photo/text message: run estimation and reply with a confirm card."""
    global _pending_seq
    chat_id = message["chat"]["id"]
    if not _authorise(client, chat_id):
        return

    # A caption accompanies a photo; plain text messages use "text".
    text = message.get("caption") or message.get("text")

    # Slash commands (/today, /help…) are handled here and RETURN EARLY —
    # they're questions about existing data, so they never reach the AI and
    # cost nothing (D8).
    if not message.get("photo") and text and text.strip().startswith("/"):
        _handle_command(client, chat_id, text)
        return

    # Telegram sends several downsized copies of a photo; the LAST is the
    # largest, which the vision model reads best.
    image_bytes = None
    if message.get("photo"):
        largest = message["photo"][-1]
        try:
            image_bytes = _download_photo(client, largest["file_id"])
        except Exception as e:  # noqa: BLE001 — surface any download failure to the user
            logger.warning("Photo download failed: %s", e)
            _send(client, chat_id, "Couldn't download that photo — try again.")
            return

    if image_bytes is None and not (text and text.strip()):
        _send(client, chat_id, "Send a meal photo, or describe what you ate.\n\n" + HELP_TEXT)
        return

    # Let the user know something is happening — the AI call takes a few seconds.
    _call(client, "sendChatAction", chat_id=chat_id, action="typing")

    try:
        # Telegram photos are always JPEG. Same service the /estimate endpoint
        # calls — one estimation codepath for web and chat alike.
        est = estimate_nutrition(image_bytes, "image/jpeg" if image_bytes else None, text)
    except EstimationError as e:
        # The service already phrases errors for humans (bad key, rate limit…).
        _send(client, chat_id, f"⚠️ {e}")
        return

    if est.kind == "unknown":
        # Couldn't identify food. Chat can't do the web wizard's manual form,
        # so point back there rather than saving a zero-calorie entry.
        _send(
            client, chat_id,
            "I couldn't identify food there. Try another photo, or add it "
            "manually in the web app.",
        )
        return

    # Park the estimate and offer the review-before-save decision as buttons.
    _pending_seq += 1
    key = str(_pending_seq)
    _pending[key] = {"estimate": est, "chat_id": str(chat_id)}
    _send(
        client, chat_id, _format_estimate(est),
        buttons=[
            {"text": "✅ Log it", "callback_data": f"log:{key}"},
            {"text": "❌ Discard", "callback_data": f"discard:{key}"},
        ],
    )


def _handle_callback(client: httpx.Client, callback: dict) -> None:
    """A ✅/❌ button tap: save through the single write path, or discard."""
    chat_id = callback["message"]["chat"]["id"]
    message_id = callback["message"]["message_id"]
    data = callback.get("data", "")

    # Answer the callback so Telegram stops the button's spinner. Best-effort:
    # an expired tap (bot was restarted) can't be answered, and that must not
    # stop us saving and confirming.
    def ack(text: str = "") -> None:
        _best_effort(client, "answerCallbackQuery",
                     callback_query_id=callback["id"], text=text)

    if not _authorise(client, chat_id):
        ack()
        return

    action, _, key = data.partition(":")
    pending = _pending.pop(key, None)
    if pending is None:
        # The estimate expired (bot restarted, or already actioned).
        ack("That estimate expired — send the meal again.")
        _best_effort(client, "editMessageReplyMarkup", chat_id=chat_id, message_id=message_id)
        return

    # Remove the buttons either way, so the decision can't be double-tapped.
    _call(client, "editMessageReplyMarkup", chat_id=chat_id, message_id=message_id)

    if action == "discard":
        ack("Discarded")
        _send(client, chat_id, "🗑️ Discarded — nothing was logged.")
        return

    # action == "log": save through the SAME create_entry the web app uses.
    est = pending["estimate"]
    payload = EntryInput(
        description=est.description,
        calories=est.calories,
        protein_g=est.protein_g,
        carbs_g=est.carbs_g,
        fat_g=est.fat_g,
        # The bot is the "client" here, so the calendar day is the bot host's
        # local date at logging time (the same day-boundary rule, applied from
        # the machine that receives the message).
        local_date=date.today().isoformat(),
        # Provenance so History/reports can tell chat-logged meals apart:
        # transcribed label vs judged estimate.
        source="label" if est.kind == "label" else "ai",
    )
    create_entry(payload)  # inherits validation + logging from the write path
    ack("Logged ✅")
    _send(client, chat_id, f"✅ Logged: {est.description}\n{_running_total_line()}")


# --- The polling loop ---------------------------------------------------------


def run() -> None:
    """Long-poll Telegram forever, dispatching each update. Blocking call."""
    if not TOKEN:
        raise SystemExit(
            "TELEGRAM_BOT_TOKEN is not set in backend/.env — add it and retry."
        )

    logger.info(
        "Telegram bot starting (owner=%s)",
        _owner_chat_id or "will be learned on first message",
    )

    # offset = the id of the next update we want. Passing "last seen + 1"
    # acknowledges everything before it, so we never reprocess a message.
    offset = None
    # Read timeout must outlast the server-side long poll, plus a margin.
    client = httpx.Client(timeout=POLL_TIMEOUT_S + 15)

    # Publish the command menu so Telegram can offer autocomplete. Failure
    # here is cosmetic only, so it must never stop the bot from starting.
    try:
        _register_commands(client)
    except Exception as e:  # noqa: BLE001
        logger.warning("Could not register the command menu: %s", e)

    while True:
        try:
            updates = _call(
                client, "getUpdates", offset=offset, timeout=POLL_TIMEOUT_S
            )
            # getUpdates returns a list here (not the usual dict result).
            for update in updates if isinstance(updates, list) else []:
                offset = update["update_id"] + 1
                if "message" in update:
                    _handle_message(client, update["message"])
                elif "callback_query" in update:
                    _handle_callback(client, update["callback_query"])
        except KeyboardInterrupt:
            logger.info("Telegram bot stopped by user")
            break
        except Exception as e:  # noqa: BLE001 — one bad update must not kill the bot
            # Transient network/Telegram hiccup: log and keep polling.
            logger.warning("Poll loop error (continuing): %s", e)


if __name__ == "__main__":
    # Enables `python -m app.telegram_bot` (what dev-bot.ps1 runs).
    run()
