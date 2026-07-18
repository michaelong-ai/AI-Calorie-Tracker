# Project Journey — how this app got built

> **This is a living document.** At the end of every sprint (or any pivot or
> painful debugging session), append to the Iteration Log and Lessons Learnt
> below — same session, while it's fresh. The point: this file is the
> reusable template for how to run the *next* greenfield project.

The method in one line: **agree what to build before deciding how; slice the
work so every step is demoable; write every decision and lesson down the day
it happens.**

---

## The phases

### Phase 1 — Functional analysis first (2026-07-05)

Before any technology talk, a business-analyst-style interview turned a
two-paragraph idea into [REQUIREMENTS.md](REQUIREMENTS.md): structured
multiple-choice questions in rounds, each with a recommended option and
trade-offs spelled out.

What made it work:

- **Contradictions got challenged, not silently resolved** ("you picked
  *text descriptions* AND *photos only* — which is it?").
- **Rejected options were recorded as Out of Scope** — a rejection is a
  decision too, and v2 candidates fell out of it for free.
- **The user's unprompted additions were treated as first-class** — the
  HTML report requirement arrived as a free-text answer to a question about
  CSV export, and became feature F5.
- The phase ended with open *technical* questions deliberately parked, not
  answered prematurely.

### Phase 2 — Technical refinement (2026-07-05)

A second interview, now wearing the engineer hat, reading the spec
adversarially: *"what would I have to guess to build this?"* Three
innocent-looking sentences turned out to hide real data-model decisions:

| Spec sentence | Hidden complexity | Resolution |
|---|---|---|
| "Past days judged against targets active at the time" | Goals can't be a settings row you overwrite | Append-only `goals` table with `effective_from` |
| "Day rolls over at local midnight" | Whose midnight? Timezones drift | Client captures `local_date` at logging time — the day is fixed forever |
| "Single user now, multi-user later" | "Multi-user ready" is a vibe until defined | `user_id` on every table, one seeded user, auth as an empty slot (`auth.py`) |

The output was [TASKS.md](TASKS.md): ~23 one-sitting tasks in 6 sprints,
every task with a **demo criterion** ("done means you can see X"), ordered
by two principles:

- **Vertical slices** — every sprint ends with something usable; the app
  was a working manual tracker after Sprint 1, before any AI existed.
- **Spike the scary thing early, build it late** — the vision-model unknown
  was probed with a throwaway script concept (S1) long before the wizard UI
  was built on top of it.

### Phase 3 — Build in sprints (2026-07-05 → 2026-07-08)

Six sprints from empty folder to feature-complete local app. The
architecture that emerged is documented in [ARCHITECTURE.md](ARCHITECTURE.md)
(system diagram, decisions log); the AI integration is explained in
plain language in the [README](README.md#how-the-ai-integration-works).
Two standing disciplines shaped every task:

- **Educational comments everywhere** (the PO is learning the stack) — every
  function says what/why in plain language.
- **Tests ship with the feature, not after** — 53 backend tests by Sprint 5,
  each locking in a spec promise (goal versioning, day filtering, the
  report's zero-external-references invariant).

### Phase 4 — Re-scope when reality votes (2026-07-09, ongoing)

The plan said "deploy early." Reality said the hosting account didn't
exist. Rather than stall, the backlog bent: deploy moved to its own
deferred sprint, and the Telegram integration was re-designed around
long polling specifically so it works *without* a deploy. A pivot that
took ten minutes of editing — because the backlog was alive and every
decision had a written home.

---

## Iteration log

*Append one entry per sprint or pivot: what shipped, what changed, what it taught.*

- **Sprint 0 (2026-07-05)** — Walking skeleton: monorepo scaffold, SQL
  migrations with a hand-rolled runner (no ORM, deliberately — SQL stays
  visible for learning), 3-tab mobile shell. Deploy task blocked on a
  hosting account and never unblocked — see Lessons #3.
- **Sprint 1 (2026-07-05)** — Manual tracker end to end: entries CRUD,
  Today screen, totals, day navigation. PO requested a test suite
  mid-sprint (D1) — it became the standing rule that features ship with
  tests.
- **Sprint 2 (2026-07-05)** — TDEE calculator (pure functions, known-answer
  tests), versioned goals, targets wired into Today. Goal versioning — the
  refinement phase's biggest catch — cost almost nothing because the schema
  was ready for it from day 0.
- **Sprint 3 (2026-07-06)** — AI wizard. Mid-sprint, the PO's label-scanning
  idea (E2) was promoted from the enhancement backlog into the sprint and
  folded into the same endpoint/prompt — cheap because it was caught before
  the endpoint was built. Live verification fought two environment battles
  (Lessons #1, #2). First real estimate: text-only "chicken rice" → 1150
  kcal with honest low confidence.
- **Sprint 4 (2026-07-05/08)** — Weight log, history vs per-day targets,
  then trend charts: hand-rolled inline SVG (no chart library) so the same
  approach could power the offline report; two stacked single-axis charts
  instead of the classic dual-axis mistake.
- **Sprint 5 (2026-07-08)** — Self-contained HTML report (a test literally
  scans the document for any external reference), empty-state audit,
  structured logging to a rotating file.
- **Re-scope (2026-07-09)** — Deploy (E4/AWS) deferred to Sprint 7 per PO:
  local-first. Telegram (E3) pulled forward and re-designed from webhooks to
  long polling so it needs no public URL. Sprint 6 = macro rings + Telegram.
- **Published (2026-07-11)** — Portfolio-grade README rebuilt (live captured
  API examples, mermaid architecture, condensed lessons) and the repo pushed
  to GitHub (michaelong-ai/AI-Calorie-Tracker). The pre-push security sweep
  caught a broken .gitignore about to stage the API key — see Lessons #8.
  Hosting analysis done (Lambda vs EC2 vs Lightsail/App Runner) ahead of
  Sprint 7.
- **PO acceptance testing (2026-07-11 → 12)** — First full hands-on pass of
  the AI wizard by the PO: meal photo, label scan + portion scaler, edit
  before save, non-food fallback, even an improvised prompt-injection
  attempt (the model ignored it). Everything passed except the quality
  verdict: **calories feel over-estimated**. That closed the long-open S1
  spike (the shipped feature became the spike) and produced three same-day
  improvements: D4 per-ingredient calorie breakdown (bottom-up estimation,
  total = sum of items — see Lessons #10), D5 DD-MMM-YYYY display dates,
  D6 History screen reordered calories-first. 53/53 tests green.

- **Sprint 6 features (2026-07-15)** — Macro rings on Today (palette
  validated for colour-blindness against the app's own light/dark surfaces;
  over-target signalled by colour *and* text), History day drill-down (D7),
  and a zero-AI food quick-pick derived from history (T6.4). PO acceptance
  round 2 passed all of them; the only false alarm ("weight still first")
  was a stale browser tab.
- **Telegram bot (2026-07-18)** — Sprint 6 closed. Meal logging by chat
  photo, long-polling so it needs no deploy (see Lessons #11). Reuses the
  existing estimation service and the single write path, so a whole new
  input channel was ~250 lines and zero changes to the core. Owner auth
  auto-learns the chat id on first message and locks via `.env`.

---

## Lessons learnt

*Append as they happen. Each one: what happened → the takeaway.*

1. **Python virtual environments don't survive folder renames.** The project
   folder was renamed and every `.exe` in the venv still pointed at the old
   path ("Fatal error in launcher"). → Venvs are disposable artifacts:
   delete and rebuild, never debug them. Launch via `python -m <tool>`,
   which is rename-proof.
2. **One machine quirk will bite you twice if you fix the symptom.** This
   machine's antivirus intercepts HTTPS with its own certificate. It broke
   pip on day 0 (fixed narrowly with `trusted-host`) and returned on day 2
   to break the AI SDK — masquerading as an invalid API key. → Fix the
   class, not the instance: `truststore` makes Python trust the OS
   certificate store, ending the whole category.
3. **"Deploy early" dies without an account.** The walking-skeleton plan
   included deploying in week 1; it stayed blocked on "PO signs up for a
   host" for the entire project. → Third-party account signup is itself a
   task with an owner and a deadline — schedule it, don't just note it.
4. **Innocent spec sentences hide data models.** "Past days judged against
   the targets active at the time" = an append-only versioned table. →
   Read specs adversarially in refinement; the cheapest schema change is
   the one made before there's data.
5. **One write path pays compound interest.** AI estimates, label scans,
   manual entry — and next, Telegram — all save through the same
   `POST /entries`. Every new input method inherits validation, logging,
   and review-before-save for free.
6. **A living backlog makes pivots cheap.** Deploy-to-Telegram re-scope took
   minutes because TASKS.md and ENHANCEMENTS.md were already true — every
   idea had a written home with its reasoning attached.
7. **The AI's honesty is a product feature you design.** The system prompt
   demands visible assumptions and a confidence level; structured outputs
   guarantee parseable JSON; the tracker is unwritable without user
   confirmation. Trust in the AI feature comes from these constraints, not
   from the model being right.
8. **`.gitignore` comments must live on their own lines.** The first
   staging attempt for GitHub included `backend/.env` (the real API key!)
   because inline comments (`backend/.venv/  # recreated from...`) are
   *part of the pattern* in gitignore syntax — every rule was silently
   broken. Caught by a pre-commit security check (`git check-ignore` on a
   list of known-sensitive files) before anything was committed. → Never
   trust ignore rules by reading them; verify with `git check-ignore` and
   a staged-files sweep before the first commit. The educational-comments
   habit is for *code*; config formats each have their own comment rules.
9. **Background dev servers die with the assistant's session.** Repeatedly
   confusing until diagnosed. → Own your servers: run `dev-backend.ps1` /
   `dev-frontend.ps1` in your own terminals; let the assistant verify via
   tests and HTTP calls.
10. **When an AI estimate feels wrong, make it auditable before making it
    "right".** The PO judged calorie totals over-estimated. Instead of just
    tuning the prompt downward (invisible, unverifiable), the fix forces the
    model to itemize every component and make the total equal the sum
    (D4). The first live test came back *higher* than before — but now the
    user can point at the exact line that's inflated ("I don't drink all
    the broth") and edit it. → For AI outputs users must trust, showing the
    working beats adjusting the answer.
11. **A new input channel is cheap when everything converges on one path.**
    The Telegram bot added a whole new way to log meals (chat photo →
    estimate → confirm → save) in ~250 lines, changing nothing in the core —
    because it just calls the existing `estimate_nutrition()` and
    `create_entry()`. The "one write path" and "one estimation codepath"
    decisions from Sprints 1 and 3 paid out again. Two integration notes
    worth keeping: long polling (bot calls Telegram, not the reverse) lets a
    local machine act as a bot server with no public URL and no deploy; and
    the machine-specific SSL-interception fix (`truststore`) has to be
    applied in *every* process that makes HTTPS calls, not just the web
    server — the bot needed its own `inject_into_ssl()`.

---

## Going forward — the checklist for each iteration

At the end of every sprint (same session as the work):

1. TASKS.md statuses are true; discovered work is filed.
2. New ideas landed in ENHANCEMENTS.md with what/why/how.
3. This file: one Iteration Log entry; any new Lessons Learnt.
4. If an external/AI integration changed: its README breakdown still tells
   the truth (single tuning point, request trace, secrets, failure modes).
5. If a structural decision changed: ARCHITECTURE.md's decisions log has a
   row for it.
