# Calorie Tracker — Project Conventions

## What this project is

Mobile-first web app: AI estimates calories/macros from meal photos or text
descriptions; user reviews/edits, confirms, and tracks daily intake against
TDEE-based targets. Functional spec: `REQUIREMENTS.md`. Sprint backlog:
`TASKS.md`.

## Key documents — keep them alive

- `REQUIREMENTS.md` — the agreed functional spec. If scope changes, update it.
- `TASKS.md` — the **living backlog**. When working on a task, mark it `[~]`;
  when done, mark it `[x]` in the same session. Newly discovered work goes
  under "Discovered tasks" with its sprint. Never leave statuses stale.
- `ENHANCEMENTS.md` — the **idea parking lot** (UI polish, nice-to-haves the
  PO mentions in passing). Capture ideas there the moment they come up —
  what/why/how-sketch, dated. Ideas only become work when promoted into
  TASKS.md. See the `backlog-keeper` skill.
- `README.md` — includes "How the AI integration works". **Standing rule:**
  any new external/AI integration ships with a plain-language README
  breakdown (single tuning point for the prompt/config, request trace,
  secret handling, response guarantees, failure modes) — written for the
  PO, in the same task that builds the integration.
- `JOURNEY.md` — the project's story and retrospective. **Standing rule:**
  at the end of every sprint, pivot, or painful debugging session, append
  an Iteration Log entry and any new Lessons Learnt — in the same session,
  while fresh. Its "Going forward" checklist is the end-of-sprint routine.
- **When asked to "continue" / "what's next"** (any session, any model):
  don't trust chat memory — reconstruct state from the files above plus
  git status, reconcile the backlog against reality (uncommitted changes,
  test suite, stale blockers), then take the highest-priority unblocked
  task. Full procedure: the `continue-project` skill.

## Stack (decided 2026-07-05, refinement session)

- Backend: **Python + FastAPI**, SQLite database
- Frontend: **React + Vite + TypeScript**, mobile-first
- AI: vision model via backend endpoint (API key server-side only, never in
  frontend code)
- Deployment: hosted full-stack (must be reachable from a phone)

## Code style — educational comments (Product Owner requirement)

The owner is learning the stack through this project. All code must be
heavily commented for a developer seeing FastAPI/React for the first time:

- **Every function** gets a docstring/comment in plain language: what it
  does, what its inputs mean, what it returns.
- **Non-obvious lines/blocks** get inline comments explaining what the step
  does *and why it's needed*.
- Favor explanatory over terse. Restating an obvious signature is not the
  goal — explaining the mechanism and the reasoning is.

## Design decisions that must not be silently violated

- **Multi-user ready:** `user_id` on every table (single seeded user for v1);
  no global singletons; auth is a future slot, not a retrofit.
- **Goal versioning:** goals are never overwritten — new row with
  `effective_from`. Historical days are judged against the goal active on
  that date; days before the first goal show totals without comparison.
- **Day boundary:** entries store UTC timestamp **plus** client-captured
  `local_date`; the calendar day is fixed at logging time.
- **Review before save:** AI estimates never write to the tracker without
  explicit user confirmation.
- **Photos are discarded** after estimation — never persisted.
- **HTML report is self-contained:** inline SVG/CSS/JS, zero external
  references; must open offline from a local file.
- **Units:** metric (kg, cm) throughout.
