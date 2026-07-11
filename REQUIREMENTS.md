# Calorie Tracker — Functional Requirements

**Status:** v1.1 — functional spec agreed 2026-07-05; technical refinement pass completed same day
**Phase:** Refined and broken into sprints — see `TASKS.md` for the living backlog.

## 1. Product Overview

A mobile-first web application that helps a user hit daily calorie and macro
goals. The user photographs (or describes) a meal, an AI agent estimates its
calories and macros, the user reviews and confirms the estimate, and it is
logged to a daily tracker measured against personalized TDEE-based targets.

## 2. Scope Decisions

| Area | Decision |
|---|---|
| Users | Single user for v1; data model must be multi-user ready (add accounts later without migration pain) |
| Platform | Mobile-first responsive web app (usable on desktop) |
| Logging inputs | Photo upload, text description, or both together |
| AI interaction | Guided upload wizard (no free-form chat): upload → estimate card → edit → save |
| Estimate handling | User always reviews/edits AI estimate before it is saved |
| Nutrition values | Calories, protein, carbs, fat only |
| Meal grouping | None — chronological list per day; day rolls over at local midnight |
| Goal targets | Fixed until user re-runs the calculator |
| Units | Metric (kg, cm) |
| Export | HTML progress report (view progress over time, shareable/openable offline) |

Decisions added during technical refinement (2026-07-05):

| Area | Decision |
|---|---|
| Architecture | Hosted full-stack: FastAPI (Python) backend + React/Vite/TypeScript frontend + SQLite — reachable from phone anywhere; API key stays server-side |
| Photo retention | Photos are discarded after estimation; only numbers + text summary stored |
| Multi-user ready (defined) | `user_id` on every table with a single seeded user; no global singletons; auth is a future slot |
| Goal history | Goals are versioned (`effective_from`), never overwritten; past days judged against the goal active on that date; days before the first goal show totals only |
| Day boundary | Entries store UTC timestamp + client-captured local calendar date; the day is fixed at logging time |
| HTML report constraint | Inline SVG/CSS/JS only, zero external references — must open offline |
| AI failure handling | Explicit scope: unidentifiable input → manual fallback in-wizard; API errors surfaced with retry; malformed model responses rejected by validation |
| Code style | Educational inline comments throughout — owner is learning the stack (see `CLAUDE.md`) |

## 3. Features

### F1 — AI Meal Estimator (guided wizard)

The core logging flow, as a step-by-step wizard rather than a chatbot:

1. **Input step:** user uploads a meal photo, types a description, or both
   (e.g. photo + "large portion, extra rice").
2. **Estimate step:** AI returns an estimate card:
   - Identified food item(s) and assumed portion size
   - Calories, protein (g), carbs (g), fat (g)
3. **Review step:** all values are editable — portion, calories, each macro.
4. **Confirm step:** user saves; entry lands in today's tracker timestamped.

Acceptance criteria:
- A photo alone is sufficient input; text alone is sufficient input.
- The AI's assumptions (portion size, preparation) are visible so the user
  knows what to correct.
- Nothing is written to the tracker until the user explicitly confirms.
- If the AI cannot identify the food, the user can fall back to entering
  values manually within the same wizard.

**Label scanning (added 2026-07-05, promoted from enhancement E2):** the
input photo may also be the **nutrition facts panel of a packaged product or
drink**. The AI then *transcribes* the printed values instead of estimating.

Additional acceptance criteria:
- A photo of a nutrition label yields the label's values, scaled by a
  serving-size question ("how much did you have?" — per serving / per 100 g /
  whole pack) answered in the review step.
- The estimate card distinguishes transcribed-from-label values from
  estimated ones (confidence differs fundamentally).

### F2 — Daily Tracker Sheet

The home screen. Shows for the current day:

- **Totals vs targets:** consumed and remaining calories/protein/carbs/fat
  against the active goal (e.g. "620 kcal left, 40 g protein to go").
- **Meal log:** chronological list of today's entries with per-entry macros;
  each entry can be edited or deleted after logging.
- **Navigation:** move to previous days to view/edit past logs.

Acceptance criteria:
- Totals update immediately when an entry is added, edited, or deleted.
- Day boundary is local midnight.
- Editing a past day's entry recalculates that day's totals.

### F3 — Macro Goal Calculator

TDEE-based target setup:

- **Inputs:** weight (kg), height (cm), age, sex, activity level,
  goal (cut / maintain / bulk) and rate (e.g. kg per week).
- **Outputs:** daily calorie target and protein/carb/fat gram targets.
- Targets are **fixed** once set; they change only when the user re-runs the
  calculator. Logged weight changes never silently adjust targets.

Acceptance criteria:
- Calculated targets become the active goal used by the tracker (F2).
- User can override any calculated number before saving it as the goal.
- Previous goals are retained historically so past days are judged against
  the targets that were active at the time.

### F4 — History, Trends & Weight Log

- Week/calendar view of past days: daily calorie totals vs target,
  adherence at a glance.
- Weekly averages for calories and macros.
- **Weight log:** user records body weight (kg) over time; weight trend is
  shown alongside intake so progress vs plan is visible.

### F5 — HTML Progress Report Export

- User can export a self-contained HTML file summarizing progress over a
  chosen period: weight trend, daily/weekly calorie and macro intake vs
  targets, adherence summary.
- The file must open standalone in any browser (no server needed).

## 4. Out of Scope (v1)

- User accounts / authentication (design for it, don't build it)
- Conversational chatbot refinement of estimates
- Meal categories (breakfast/lunch/dinner/snack)
- Saved/favorite meals for one-tap re-logging
- Fiber, sugar, micronutrients
- Auto-adjusting targets from weight changes
- Barcode scanning, food-database search
- CSV export, imperial units

These are natural v2 candidates; the data model should not preclude them.

## 5. Open Items for Solution Architecture Phase

Resolved during refinement (2026-07-05) — see the second table in Section 2:

- ~~Where data lives~~ → hosted full-stack, SQLite (upgradeable to Postgres)
- ~~Web stack~~ → FastAPI backend + React/Vite/TypeScript frontend
- ~~Photo upload/storage~~ → uploaded to backend for estimation, then discarded
- ~~How the HTML report is generated~~ → backend-rendered, self-contained,
  inline SVG

Still open:

- AI provider/model choice and cost per scan — to be settled by the Sprint 1
  spike (task S1 in `TASKS.md`)
- Hosting provider choice — to be settled in Sprint 0 deploy task (T0.4)
