# Architecture

> Written during Sprint 0. This document describes the system's shape and the
> reasoning behind it; fold the relevant parts into README.md when the project
> is ready to present. Keep it updated when structural decisions change.

## System overview

Classic three-part web application, one repository:

```
 ┌─────────────────────┐        HTTP/JSON         ┌──────────────────────┐
 │  Frontend (phone)   │ ───────────────────────▶ │  Backend API         │
 │  React + TypeScript │ ◀─────────────────────── │  Python + FastAPI    │
 │  built with Vite    │                          │                      │
 └─────────────────────┘                          │  ┌────────────────┐  │
        the only part the                         │  │ SQLite database │  │
        user ever touches                         │  └────────────────┘  │
                                                  └──────────┬───────────┘
                                                             │ server-side only
                                                             ▼
                                                  ┌──────────────────────┐
                                                  │  Vision model API    │
                                                  │  (meal photo/text →  │
                                                  │   calories & macros) │
                                                  └──────────────────────┘
```

**Why a backend at all?** Two reasons. (1) The AI vision call needs an API
key, and any key shipped in browser JavaScript is public — so the model is
only ever called server-side. (2) Data must outlive any single browser and be
reachable from the phone anywhere, which means a hosted server and database.

## The pieces

### Frontend — `frontend/`

React single-page app, written in TypeScript, built by Vite. Mobile-first:
the primary user is on a phone at a meal. It never talks to the AI provider
or the database directly — everything goes through the backend's JSON API.

- `src/main.tsx` — browser entry point; mounts the app into `index.html`
- `src/App.tsx` — root component; will hold the Today / Goals / History shell (T0.3)

### Backend — `backend/`

FastAPI application serving a JSON API. Owns all business logic: TDEE math,
goal versioning, day-total aggregation, and the vision-model call.

- `app/main.py` — creates the FastAPI app, CORS config, `/health` endpoint;
  runs database migrations at startup (lifespan)
- `app/db.py` — the only door to the database: connection factory (foreign
  keys on, dict-style rows) + migration runner
- `migrations/*.sql` — numbered, append-only plain-SQL migration files;
  applied migrations are tracked in a `schema_migrations` table, so any
  environment converges by replaying the missing ones in order
- Feature modules arrive per sprint: entries (S1), goals/TDEE (S2),
  estimation (S3), weights (S4), report (S5)
- Interactive API docs are auto-generated at `/docs` — use them to test
  endpoints without the frontend

### Database — SQLite

Single-file database, zero administration — right-sized for one user, and
the schema is written so a later move to Postgres is mechanical, not a
redesign. Schema arrives in task T0.2; its non-negotiable rules:

| Rule | Why |
|---|---|
| `user_id` on every table (one seeded user for now) | "Multi-user ready": adding accounts later is an auth feature, not a data migration |
| Goals are append-only rows with `effective_from` | Past days must be judged against the goal active *on that date* |
| Entries store UTC timestamp **and** client-captured `local_date` | The calendar day is fixed at logging time — immune to timezone drift |
| No image columns anywhere | Photos are estimated, then discarded (privacy + storage decision) |

## Key data flows

**Logging a meal by photo (the core loop, Sprint 3):**
1. Phone browser uploads photo (and/or text) to `POST /estimate`
2. Backend forwards it to the vision model, validates the structured response
   (foods, portion assumptions, kcal/protein/carbs/fat), discards the image
3. Frontend shows the estimate card; user edits values; nothing is saved yet
4. On confirm, frontend calls the ordinary entries API — the same endpoint
   manual entry uses. The AI path and the manual path converge before the
   database, so there is exactly one write path to keep correct.

**Daily totals vs targets (Sprints 1–2):**
Entries for a `local_date` are summed and compared against the goal row
whose `effective_from` most recently precedes that date.

## Decisions log

| Decision | Choice | Why |
|---|---|---|
| Hosting posture | Hosted full-stack | Usable from phone anywhere; key stays server-side |
| Backend language | Python + FastAPI | PO preference; strong fit for the AI-calling side |
| Frontend | React + Vite + TS | Mainstream, fast dev loop, typed |
| DB | SQLite → Postgres later | Zero ops now, clean upgrade path |
| Photos | Discarded after estimation | Privacy, storage cost, PO decision |
| Report export | Self-contained HTML, inline SVG | Must open offline with no external references |
| DB access | stdlib `sqlite3` + plain-SQL migrations, no ORM | Learning project: SQL stays visible; a tiny commented runner teaches what migrations are. Revisit if query complexity grows |
| Code style | Educational comments everywhere | PO is learning the stack (see CLAUDE.md) |

## Local development environment notes

- **Ports:** backend `:8000`, frontend `:5173`; CORS in `app/main.py` allows
  the frontend origin explicitly.
- **This machine has SSL interception** (antivirus/proxy re-signs HTTPS).
  Windows trusts it; Python's own cert bundle doesn't. `backend/.venv/pip.ini`
  therefore sets `trusted-host` for PyPI. npm is unaffected. Expect the same
  issue if Python ever calls external APIs directly — may need `certifi`
  configuration or the OS trust store (`truststore` package) in Sprint 3.
- Node.js LTS was installed via winget on 2026-07-05 (was absent).
