# Calorie Tracker — Sprint Backlog

**This is the living backlog.** Claude updates task statuses here as work
proceeds and adds newly discovered tasks under the relevant sprint. Do not
let this file drift from reality — status changes happen in the same session
as the work.

**Legend:** `[ ]` todo · `[~]` in progress · `[x]` done · `[!]` blocked (reason noted)

**Task sizing:** each task is completable and demoable in one sitting (~1–2 h).
Every task lists a **Demo** criterion — the observable proof it's done.

**Standing rule for all code tasks:** educational inline comments everywhere —
every function gets a plain-language docstring (purpose, inputs, returns), and
non-obvious lines get comments explaining what *and why*. Written for a
developer seeing FastAPI/React for the first time. See CLAUDE.md.

**Stack (decided in refinement, 2026-07-05):** FastAPI (Python) backend ·
React + Vite + TypeScript frontend · SQLite · hosted full-stack · photos
discarded after estimation.

---

## Sprint 0 — Walking skeleton
*Sprint demo: a deployed "hello" app reachable from your phone.*

- [x] **T0.1 — Scaffold monorepo** *(covers: foundation)* ✅ 2026-07-05
  FastAPI backend + Vite React TS frontend in one repo (`backend/`,
  `frontend/`), with dev scripts to run both locally.
  **Demo:** both servers start with one documented command each; frontend
  loads in browser.
  *Done: `dev-backend.ps1` / `dev-frontend.ps1`; /health verified; frontend
  serves placeholder page. Env notes: Node LTS installed via winget; pip SSL
  workaround in `backend/.venv/pip.ini` (see README troubleshooting).*

- [x] **T0.2 — SQLite schema v1 + migrations** *(covers: F1–F4 data model; depends: T0.1)* ✅ 2026-07-05
  Tables: `users` (seeded single user), `entries`, `goals` (with
  `effective_from`, never overwritten), `weights`. `user_id` on every table —
  the "multi-user ready" obligation. Entries store UTC timestamp **and**
  client-captured `local_date` (day is decided at logging time).
  **Demo:** migration runs from empty; seeded user visible via a DB query.
  *Done: plain-SQL migrations (`backend/migrations/*.sql`) + runner in
  `app/db.py`, applied at startup via FastAPI lifespan. Verified: empty →
  5 tables, user "Mike" seeded, FK + CHECK constraints enforced, re-run
  idempotent. No ORM by design (see ARCHITECTURE.md).*

- [x] **T0.3 — Mobile-first app shell** *(depends: T0.1)* ✅ 2026-07-05
  Layout + navigation (Today / Goals / History), styled for phone screens;
  calls a backend `/health` endpoint and shows the result.
  **Demo:** shell renders on a phone-sized viewport; health check round-trips.
  *Done: 3-tab shell with bottom nav (`App.tsx`), health status dot, typed
  API layer (`api.ts` + `types.ts`), mobile-first CSS with dark mode.*

- [>] **T0.4 — Deploy the skeleton** *(depends: T0.1–T0.3)*
  Pick host, deploy backend + frontend, wire env vars. Deployment pain
  surfaces in week 1, not week 6.
  **Demo:** app opens on your actual phone over mobile data.
  *SUPERSEDED 2026-07-09: host decision resolved as AWS (enhancement E4);
  scoped into Sprint 6 as T6.2 (containerize) + T6.3 (deploy). The "deploy
  early" intent didn't survive the blocker — lesson noted: it deployed
  last, not first.*

## Sprint 1 — Manual tracker (no AI yet)
*Sprint demo: log lunch by hand on your phone; totals update. Covers F2 (partial).*

- [x] **T1.1 — Entries API** *(covers: F2; depends: T0.2)* ✅ 2026-07-05
  CRUD endpoints for meal entries (description, kcal, protein, carbs, fat,
  timestamp, `local_date` from client).
  **Demo:** create/edit/delete an entry via API docs (`/docs`); survives restart.
  *Done: `app/routers/entries.py` + auth slot (`app/auth.py`). Verified over
  HTTP: create/list/update/delete, negative values rejected (422),
  missing ids → 404.*

- [x] **T1.2 — Today screen: entry list** *(covers: F2; depends: T1.1, T0.3)* ✅ 2026-07-05
  Chronological list of today's entries with edit and delete. Manual-entry
  form (this later becomes the AI wizard's fallback and reuses its save path).
  **Demo:** add, edit, delete an entry from the phone UI.
  *Done in `screens/Today.tsx`. Awaiting PO hands-on test.*

- [x] **T1.3 — Daily totals summary** *(covers: F2; depends: T1.2)* ✅ 2026-07-05
  Consumed kcal/protein/carbs/fat for the day, updating immediately on any
  entry change. ("Remaining vs target" lights up in Sprint 2.)
  **Demo:** totals change the moment an entry is added/edited/deleted.
  *Done: totals are derived from the entries array each render — cannot go
  stale by construction.*

- [x] **T1.4 — Past-day navigation** *(covers: F2; depends: T1.3)* ✅ 2026-07-05
  Move to previous days; view and edit past entries; that day's totals
  recompute.
  **Demo:** edit yesterday's entry, see yesterday's totals change.
  *Done: ‹ › day navigation; future days blocked; entries editable on any day.*

- [x] **S1 — SPIKE: vision-model estimation quality** *(de-risks Sprint 3; timeboxed 1 sitting)* ✅ 2026-07-11
  Standalone script: send 5–10 test food photos (+ text variants) to the
  vision model; evaluate estimate quality; settle the JSON response schema
  and prompt. Throwaway code — findings recorded at the bottom of this file.
  **Demo:** written findings: model choice, prompt, schema, rough cost/scan.
  *CLOSED via live app testing instead of a standalone script (the feature
  shipped first, so the spike became the PO's hands-on pass). Findings in
  "Spike findings" below; headline: quality good, calories skew HIGH →
  mitigation D4 (per-ingredient breakdown for auditability).*

## Sprint 2 — Goals
*Sprint demo: calculator produces targets; Today shows "X kcal left". Covers F3.*

- [x] **T2.1 — TDEE calculation service** *(covers: F3; depends: T0.1)* ✅ 2026-07-05
  Mifflin-St Jeor + activity multipliers + goal-rate adjustment as pure
  Python functions with unit tests. Inputs: weight/height/age/sex/activity/
  goal+rate. Outputs: kcal + protein/carb/fat gram targets.
  **Demo:** unit tests pass with known-answer cases.
  *Done: `app/services/tdee.py`, 10 known-answer tests in `test_tdee.py`.
  Macro split: protein 1.8 g/kg, fat 25% kcal, carbs remainder.*

- [x] **T2.2 — Goal calculator UI** *(covers: F3; depends: T2.1, T0.2)* ✅ 2026-07-05
  Form → computed targets preview → user can override any number → save.
  Saving creates a **new goal version** (`effective_from` = now); history kept.
  **Demo:** save a goal, change inputs, save again — two versions in DB.
  *Done: `routers/goals.py` (/calculate pure, POST append-only, /active
  per-date lookup) + `screens/Goals.tsx` with BMR/TDEE working shown and
  goal-history list. Versioning locked in by `test_goals.py`.*

- [x] **T2.3 — Targets wired into tracker** *(covers: F2+F3; depends: T2.2, T1.3)* ✅ 2026-07-05
  Today shows consumed / remaining vs the active goal ("620 kcal left, 40 g
  protein to go"). Past days compare against the goal active **on that
  date**; days before the first goal show totals only.
  **Demo:** yesterday judged against yesterday's goal after saving a new one today.
  *Done: Today fetches the goal for the SELECTED date; totals show
  consumed/target, kcal-left line (red when over), pre-goal days plain.*

## Sprint 3 — AI estimation wizard
*Sprint demo: photo of a meal → estimate card → edit → it's in the tracker. Covers F1.*

- [x] **T3.1 — `/estimate` endpoint** *(covers: F1 incl. E2 label scanning; depends: T0.2, S1)* ✅ 2026-07-06
  *`services/estimation.py` + `routers/estimate.py`: Claude vision call
  (default `claude-opus-4-8`, overridable via ESTIMATE_MODEL), structured
  outputs guarantee valid JSON, estimate/label/unknown modes in one prompt,
  image discarded after response. Migration 002 adds the 'label' source.
  9 tests with mocked model. LIVE-VERIFIED with real key (text estimate:
  chicken rice → 1150 kcal with sensible assumptions, confidence=low).
  Needed the truststore SSL fix — see README troubleshooting.*
  Accepts image and/or text → vision model → validated JSON. The model
  distinguishes two modes in one prompt: **plate of food → estimate** vs
  **nutrition label → transcribe** the printed values. Response carries
  `kind: "estimate" | "label"` plus, for labels, the basis (per-100g /
  per-serving + serving size) so the UI can do portion math. Image bytes
  discarded after the response (decision: no photo retention).
  **Demo:** POST a food photo → estimate; POST a label photo → transcribed
  values, both via `/docs`.
  *Schema note: entries.source CHECK currently allows 'manual'|'ai' —
  migration 002 adds 'label' when this lands.*

- [x] **T3.2 — Wizard: input + estimate card** *(covers: F1 incl. E2; depends: T3.1, T0.3)* ✅ 2026-07-11
  *CODE COMPLETE 2026-07-06; PO HANDS-ON VERIFIED 2026-07-11: real meal
  photo → estimate card ✓; nutrition-label photo → transcribed card with
  working portion scaler ✓ (one product tested).*
  Step 1: upload photo and/or type description. Step 2: estimate card
  showing foods, **visible assumptions** (portion, preparation), and macros.
  Label scans get a visibly different card ("read from label") and a
  **serving-size question** ("how much did you have?") that scales the values.
  **Demo:** phone camera photo → estimate card; label photo → transcribed
  card with portion selector.

- [x] **T3.3 — Wizard: review, edit, confirm** *(covers: F1 incl. E2; depends: T3.2, T1.1)* ✅ 2026-07-11
  *CODE COMPLETE 2026-07-06; PO HANDS-ON VERIFIED 2026-07-11: edited a
  value, saved, entry appeared with the edited number and totals updated.*
  Step 3: every value editable. Step 4: confirm → saves through the existing
  entries API. Nothing is written until confirm.
  **Demo:** correct the AI's portion guess, save, entry appears in Today;
  same flow works for a scanned label.

- [x] **T3.4 — Wizard failure paths** *(covers: F1; depends: T3.3)* ✅ 2026-07-11
  Unidentifiable food → manual-entry fallback inside the wizard; API
  error/rate-limit messaging with retry; malformed model response rejected
  by validation, never saved.
  *CODE COMPLETE 2026-07-06; PO HANDS-ON VERIFIED 2026-07-11: non-food
  photo → manual fallback ✓; PO also tried a prompt-injection-style fake
  description — the model ignored the instructions and behaved correctly ✓.*
  **Demo:** photo of a non-food object lands you in manual fallback, not a crash.

## Sprint 4 — History, trends & weight
*Sprint demo: calendar of days vs targets and a weight trend. Covers F4.*

- [x] **T4.1 — Weight log** *(covers: F4; depends: T0.2)* ✅ 2026-07-05
  API + UI to record body weight (kg) over time; list + delete.
  **Demo:** log a weight from the phone, see it in the list.
  *Done: `routers/weights.py` + weight card on History screen (log, recent
  five, delete). Tests in `test_weights.py`.*

- [x] **T4.2 — Week/calendar history view** *(covers: F4; depends: T2.3)* ✅ 2026-07-05
  Past days at a glance: daily kcal total vs target-active-that-day,
  adherence coloring.
  **Demo:** a week of logged days renders with over/under indication.
  *Done: `routers/days.py` (per-day totals paired with the goal active that
  day; `test_days.py`) + last-14-days list on History with green/red
  adherence coloring (within = up to 5% over). Calendar-grid layout and
  charts fold into T4.3.*

- [x] **T4.3 — Trends: averages + weight vs intake** *(covers: F4; depends: T4.1, T4.2)* ✅ 2026-07-08
  Weekly kcal/macro averages; weight trend charted alongside intake.
  **Demo:** chart shows weight line and weekly average intake together.
  *Done: `routers/trends.py` (weekly buckets, per-logged-day averages,
  continuous week span; `test_trends.py`) + hand-rolled inline-SVG
  `components/charts.tsx` (LineChart + BarChart, no library so they reuse in
  the offline HTML report) + Trends card on History. Colors from the
  validated dataviz palette as CSS vars (light/dark). Deliberately two
  stacked single-axis charts, NOT a dual-axis plot. Live-verified /trends
  bucketing over seeded data.*

## Sprint 5 — Report & polish
*Sprint demo: exported HTML report opens offline with charts. Covers F5.*

- [x] **T5.1 — Self-contained HTML report** *(covers: F5; depends: T4.3)* ✅ 2026-07-08
  Export for a chosen period: weight trend, intake vs targets, adherence
  summary. Inline SVG charts, zero external references — must open from a
  local file with no network.
  **Demo:** exported file opens in a browser in airplane mode, charts intact.
  *Done: `services/report.py` (document) + `services/report_charts.py`
  (Python twin of charts.tsx) + `routers/report.py` (GET /report, download
  headers, reuses trends/days/goals functions). Download link on History.
  Tests include a self-containment scan (no link/script/src/url()/http) and
  the empty-database case. Sample generated to PO's Downloads and verified:
  2 SVGs, 5.5 KB, zero external refs.*

- [x] **T5.2 — Empty states & first-run** *(depends: T2.3, T3.3)* ✅ 2026-07-08
  No-data experiences: first launch, day with no entries, no goal set yet,
  history before any logging.
  **Demo:** fresh database walk-through hits no blank/broken screens.
  *Done: audited all screens. Already covered: empty day, no-goal Goals
  screen, empty history, hidden trends card, wizard failure fallbacks,
  empty-DB report (tested). Added: Today's no-goal nudge ("use the Goals
  tab to calculate your targets"). PO fresh-phone walkthrough happens as
  part of T5.3.*

- [ ] **T5.3 — End-to-end smoke pass** *(depends: everything)*
  Full loop on the real phone: calculate goal → photo-log a meal → check
  totals → log weight → export report. Fix papercuts found.
  **Demo:** the loop completes without touching a desktop.

## Sprint 6 — Telegram on local *(scoped 2026-07-09 from E1/E3; re-scoped same day: deploy removed per PO — local-first, Telegram first)*
*Sprint demo: from your phone, anywhere, send a meal photo to your Telegram
bot — the estimate comes back in chat, you tap ✅, and the entry is in your
local tracker. Plus macro rings on Today.*

*Key design point: the bot uses LONG POLLING (`getUpdates`), not webhooks —
our local backend calls out to Telegram's servers, so no public URL, no
deploy, no router config. Telegram is the middleman: phone works anywhere,
tracker stays on the PC (which must be on). Webhooks become a cheap swap
later when the app deploys (Sprint 7).*

- [ ] **T6.1 — Macro rings on Today** *(from E1; no dependencies)*
  Replace the plain-text totals bar with four SVG progress rings — calories,
  protein, carbs, fat — each filling toward its target (fitness-app style).
  Distinct over-target treatment (ring turns the danger color); no-goal days
  fall back to the current plain totals; colors from the validated dataviz
  palette, light AND dark mode. Reuse the ring in the HTML report if cheap.
  **Demo:** log a meal, watch the rings fill; go over target, ring turns red.

- [!] **T6.2 — Telegram bot: polling skeleton + estimate reply** *(from E3)*
  Long-polling listener in the backend (started with the server or via a
  `dev-bot.ps1` runner); `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` in .env;
  messages from any other chat id are refused (the auth slot's first real
  customer). Photo (Telegram file download) and/or caption/text → the
  existing estimation service → reply with the estimate card as text
  (description, assumptions, kcal/P/C/F, confidence; label scans include
  the basis).
  **Demo:** send the bot a meal photo from your phone, get the estimate back.
  *BLOCKED on PO (2 minutes, free): create the bot in Telegram — message
  @BotFather → /newbot → copy the token into backend/.env. First message to
  the bot will reveal your chat id; task includes surfacing it for .env.*

- [ ] **T6.3 — Telegram bot: confirm to tracker** *(from E3; depends: T6.2)*
  Inline buttons on the estimate reply (✅ log / ❌ discard) — review-before-
  save preserved in chat form; ✅ saves through the same entries write path
  with the right source ('ai'/'label'); reply confirms with the day's new
  running total vs target.
  **Demo:** tap ✅ in Telegram, entry appears in the web app's Today list.

- [ ] **T6.4 — Food library: quick-pick previously scanned foods** *(from E6; PROMOTED 2026-07-15 per PO; no dependencies)*
  On the **manual add** option (Today's entry form and the wizard's manual
  fallback), show a dropdown of previously logged foods — each option is
  the food's AI-given name plus its total calories (e.g. "Laksa — 800
  kcal"). Picking one pre-fills the whole form (kcal + macros), still
  editable before save — portion varies day to day. No AI call, instant,
  free.
  **Design (PO-chosen variant of E6a — derive from history):** new backend
  endpoint returning distinct previous entries grouped by description
  (latest values win, ordered by frequency then recency, AI/label-scanned
  foods included — they're the ones worth caching). Saves through the
  single write path (`POST /entries`) with source='manual'. No schema
  change needed. De-dup gotcha noted in E6 ("chicken rice" vs "chicken
  rice large") accepted for v1 — the list IS your history.
  **Demo:** scan a meal once; next day, add it again from the dropdown in
  two taps with zero AI wait.

## Sprint 7 — Deploy (deferred 2026-07-09 per PO: local-first for now)
*Sprint demo: the app at a public HTTPS URL on the phone's home screen;
closes with T5.3, the full-phone smoke test.*

- [ ] **T7.1 — Containerize: one deployable unit** *(from E4)*
  Dockerfile that builds the frontend and has FastAPI serve the static files
  (kills CORS config in prod); `DATABASE_PATH` + CORS origins via env vars;
  volume-ready DB location; local `docker run` proof.
  **Demo:** one container runs locally; app + API + DB survive a container
  restart via the mounted volume.

- [!] **T7.2 — Deploy to AWS** *(from E4; resolves T0.4's host decision; depends: T7.1)*
  App Runner or Lightsail (decide by price at setup); SQLite on persistent
  storage; ANTHROPIC_API_KEY + Telegram token as secrets; HTTPS URL; switch
  the bot from polling to webhook; "Add to Home Screen" walkthrough.
  **Demo:** app opens on the phone over mobile data; wizard scan works.
  *BLOCKED on PO: AWS account + credentials. Scoped and ready.*

---

## Discovered tasks
*(added during implementation as they surface — with the sprint they belong to)*

- [x] **D1 — Backend unit test suite** *(Sprint 1; PO request 2026-07-05)* ✅
  pytest + FastAPI TestClient against a temp database per test. 12 tests:
  migrations/seeding (`tests/test_db.py`) and entries CRUD + validation
  (`tests/test_entries.py`). Run with `.\run-tests.ps1`. Future feature
  tasks (TDEE, estimate endpoint) must ship with tests in this suite.

- [x] **D3 — README: plain-language AI-integration breakdown** *(Sprint 3; PO request 2026-07-06)* ✅
  README section "How the AI integration works": where the system prompt
  lives (`SYSTEM_PROMPT` in `services/estimation.py`), the photo's journey
  end to end, why structured outputs guarantee valid JSON, and the
  guardrails (key handling, photo discarded, read-only estimate, single
  write path). Standing rule: any new external/AI integration gets the same
  README treatment (also added to the ba-interview skill's hand-off notes).

- [x] **D2 — Structured logging + log file** *(Sprint 5, alongside T0.4; PO request 2026-07-05)* ✅ 2026-07-08
  Replace bare uvicorn console output with configured Python logging:
  timestamps, levels, app events (entry created, goal saved, AI call
  made/failed), request durations, written to a rotating log file. Needed
  once the app runs on a host with no terminal to watch.
  **Demo:** a log file shows a timestamped line for an entry created via the UI.
  *Done: `app/logging_config.py` (console + rotating file at
  `backend/logs/app.log`, 1 MB × 3 backups, gitignored) + request-duration
  middleware in main.py + app-event lines for entry created, goal saved, AI
  estimate requested/ok/failed. Demo verified: POST /entries produced
  "Entry created: id=4 … (8 ms)" in the file. Note: running the test suite
  also writes to this log (harmless in dev; revisit at deploy).*

- [x] **D4 — Per-ingredient calorie breakdown in estimates** *(Sprint 6; PO request 2026-07-11 from S1 finding "calories feel over-estimated")* ✅ 2026-07-12
  Schema + model gain `items: [{name, calories}]`; prompt now demands
  BOTTOM-UP estimation (itemize components, total = sum of items, no
  padding margin per component) alongside the realism guidance. Wizard
  shows the breakdown as a table above the editable fields. Live-verified:
  laksa → 7 components summing exactly to the total. NOTE: breakdown makes
  totals *auditable*, not automatically lower — user can now challenge the
  specific line that looks inflated.

- [x] **D5 — DD-MMM-YYYY display dates** *(Sprint 6; PO request 2026-07-11)* ✅ 2026-07-12
  `formatDate()` in api.ts + `_display_date()` in report.py: all user-facing
  dates render as e.g. 12-Jul-2026 (Today header, History day rows, weight
  list, goal history, report table/label). ISO stays the storage/API format.

- [x] **D6 — History screen: calories before weight** *(Sprint 6; PO request 2026-07-11)* ✅ 2026-07-12
  New order: Trends (calorie bars first, weight line second) → last-14-days
  list → body-weight log card → report download link.
  *2026-07-15: PO reports still seeing the weight tracker first — the code
  order is verified calories-first, so this smells like a stale browser tab.
  UAT step: hard-refresh (Ctrl+F5) on http://localhost:5173 and re-check;
  reopen this task if weight is still first after that.*

- [ ] **D7 — History: tap a day to see its meals** *(Sprint 6; PO request 2026-07-15 from UAT round 2)*
  Each row in the last-14-days list should open up to show that day's
  individual entries — what was eaten (including AI-scanned meals), each
  with its kcal — not just the day total.
  **How (sketch):** cheapest path reuses what exists — tapping a day row
  either (a) expands inline, fetching that day's entries via the existing
  entries API filtered by `local_date`, or (b) jumps to the Today tab
  already set to that date (past-day view is built, T1.4). Decide at
  implementation.
  **Scope note for PO:** this shows the day's *meal list*. The
  per-INGREDIENT breakdown (D4's items table) is shown at scan time but
  NOT saved — entries store only description + macros (photos and raw AI
  responses are discarded by design). If you want the ingredient lines
  kept for past meals too, that's a schema change (new column/table) —
  say so and it becomes its own task.
  **Demo:** tap a past day in History, see the meals logged that day.

## Spike findings
*(S1 results go here: model, prompt, response schema, cost per scan)*

- **2026-07-06, first live test (text-only):** model `claude-opus-4-8` with
  structured outputs. Input "chicken rice, large portion with extra rice and
  a fried egg" → identified Hainanese chicken rice, 1150 kcal / P55 / C115 /
  F50, five explicit assumptions (portion weights, cooking fat, hawker-style
  bias), confidence honestly reported as "low" for text-only. Schema and
  prompt behave as designed. STILL TO TEST (needs PO's real photos): photo
  estimates, nutrition-label transcription accuracy, cost per scan from
  usage data.
- **2026-07-11, PO hands-on pass (photos):** meal-photo estimate ✓; label
  transcription ✓ with working portion scaler (1 product); non-food photo →
  correct fallback ✓; injection-style fake description ignored by the
  model ✓. **Quality verdict: calories feel OVER-estimated** (likely pushed
  by the prompt's "hawker portions are larger and oilier" realism bias).
  Mitigation D4: per-ingredient calorie breakdown in the response so the
  user can see which component inflates the total, plus a prompt line
  against padding. Model stays `claude-opus-4-8` for now; revisit cost
  after a week of real usage data in the Anthropic console.
