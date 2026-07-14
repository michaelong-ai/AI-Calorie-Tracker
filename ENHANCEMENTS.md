# Enhancement Backlog

Ideas noticed along the way — UI polish, nice-to-haves, "later" features.
This is the **idea parking lot**, separate on purpose from `TASKS.md` (the
committed sprint work): writing an idea here costs nothing and loses nothing,
and nothing here is a promise until it's promoted into a sprint.

**Lifecycle:** `[ ]` idea → `[>]` promoted to TASKS.md (note the task id) → `[x]` shipped · `[-]` rejected (keep it, with the why)

Each idea records: what, why it's worth doing, and any sketch of how — enough
that picking it up weeks later needs no archaeology.

---

## UI / UX

- [>] **E1 — Macro rings: friendlier daily tracker display** *(PO, 2026-07-05 — PROMOTED 2026-07-09 into Sprint 6 as T6.1)*
  Replace the plain-text totals bar on Today with **circular progress rings**
  — one ring per metric (calories, protein, carbs, fat), each filling toward
  its target with its own color, in the style fitness apps use.
  **Why:** the current totals bar is functional but boring; the daily
  glance-value of the app deserves a display you *want* to look at.
  **How (sketch):** inline SVG circles (no chart library needed) — a
  background track + a colored arc whose length = consumed/target;
  over-target state needs a distinct treatment (e.g. ring turns the danger
  color). Color choices should pass contrast in light AND dark mode.
  Bonus: the same ring component can be reused in the HTML report (T5.1).

## Features

- [x] **E2 — Nutrition-label scanning for packaged products & drinks** *(PO, 2026-07-05 — promoted into Sprint 3; SHIPPED 2026-07-06 in T3.1–T3.3: label mode live in the wizard incl. serving-size scaler. PO hands-on label-photo test still pending as part of T3.2's demo)*
  The AI scan shouldn't be limited to pictures of prepared food: photograph
  the **nutrition facts panel** on a sealed supermarket product or drink and
  have its values read straight off the label into the tracker.
  **Why:** label reading is *more accurate* than food-photo estimation (the
  numbers are printed, not guessed) and covers a huge share of real intake —
  snacks, drinks, ready meals.
  **How (sketch):** likely NOT a separate feature — the same `/estimate`
  endpoint (T3.1) can handle it: vision models read labels well, and the
  prompt can distinguish "plate of food → estimate" from "nutrition label →
  transcribe". Two gotchas: (1) serving-size math — labels state per-100g /
  per-serving, so the wizard must ask/confirm how much was consumed;
  (2) the estimate card should show `source: label` vs `estimated` since
  confidence differs hugely. **Action now:** include 2–3 nutrition-label
  photos in the S1 spike test set so prompt + schema cover this case from
  day one.

- [>] **E3 — Telegram bot: log meals by sending a photo in chat** *(PO, 2026-07-05 — PROMOTED 2026-07-09 into Sprint 6 as T6.2 + T6.3, re-scoped to LONG POLLING so it runs against the local server with no deploy; webhook swap deferred to Sprint 7)*
  Integrate with Telegram so a meal (or label) photo sent to a bot chat gets
  estimated and logged — no need to open the web app at all.
  **Why:** Telegram is already open when eating out; removing the
  open-app-upload friction makes logging far more likely to actually happen.
  **How (sketch):** a Telegram Bot API webhook endpoint on the FastAPI
  backend (`python-telegram-bot` or raw webhook); photo → same `/estimate`
  pipeline → bot replies with the estimate card as a message with **inline
  buttons** (✅ log / ✏️ adjust / ❌ discard) — preserving the
  review-before-save rule in chat form. Needs: bot token in server env,
  mapping the Telegram chat id to our user (the auth slot's first real
  customer!), and a deployed backend with a public URL (depends on T0.4).
  Requires webhook reachability — pairs naturally with E4.

- [>] **E6 — Food library: cache frequent foods, skip the LLM** *(PO, 2026-07-11, mid-testing — PROMOTED 2026-07-15 into Sprint 6 as T6.4, as variant (a) derive-from-history: a dropdown of previously scanned foods with AI name + calories on the manual add form)*
  A growing list of foods the user has eaten before, selectable in one tap —
  "if I ate it before, I shouldn't need to call the AI again."
  **Why:** three wins at once — instant logging for repeat meals (no 5–15s
  AI wait, which is the bigger prize), zero API cost for the foods that make
  up most real diets, and it works offline/when the AI is down. Notably:
  "saved/favorite meals" was in the ORIGINAL spec's Out-of-Scope list as a
  v2 candidate — this is it maturing, now with a cost rationale.
  **How (sketch):** two candidate designs, decide at promotion time:
  (a) *zero-effort* — derive "frequents" from existing `entries` history
  (GROUP BY description, count, recency-weighted) and show a quick-pick row
  in the add flow; no schema change, but duplicate/near-duplicate
  descriptions ("chicken rice" vs "chicken rice large") pollute the list;
  (b) *explicit* — a ⭐ "save as favorite" on any entry/estimate into a new
  `favorites` table (user_id as always), cleaner names, one more tap of
  friction. Either way the pick pre-fills the normal entry form (still
  editable — portion varies day to day) and saves through the single write
  path with source='manual'. Pairs beautifully with the Telegram bot later:
  "/again chicken rice" logs without any AI call.

- [ ] **E5 — PWA: installable home-screen app** *(suggested during the
  phone-access discussion, 2026-07-09 — idea only, not scheduled)*
  Beyond plain "Add to Home Screen": a web-app manifest (name, icon, theme
  color, standalone display) so the installed app launches full-screen with
  a proper icon, plus optionally a service worker for an offline app shell.
  **Why:** makes the deployed web app feel native on the phone at near-zero
  cost; the natural finishing touch after T6.3.
  **How (sketch):** `manifest.webmanifest` + icons in `frontend/public/`,
  `<link rel="manifest">` in index.html, theme-color meta. Service worker
  only if offline shell proves worth it — the app is useless offline anyway
  (API-dependent), so maybe manifest-only.

## Infrastructure

- [>] **E4 — Deploy to AWS for always-on availability** *(PO, 2026-07-05 — PROMOTED 2026-07-09, then same-day DEFERRED to Sprint 7 as T7.1 + T7.2 per PO: local-first, Telegram integration first)*
  Host the app on AWS so it's reliably reachable from anywhere, anytime.
  **Why:** the tracker only works as a habit if it's *always* there when
  eating; a laptop that's asleep isn't a server. (Honest note: nothing
  offers literally 100% uptime — AWS SLAs are ~99.9%; that's plenty here.)
  **How (sketch):** this is really **the T0.4 host decision** — promoting
  this = choosing AWS as the host. Simplest sensible AWS shapes: (a) App
  Runner or Lightsail running the single container (FastAPI serving built
  frontend), SQLite on an attached volume — cheapest, fits v1; (b) ECS
  Fargate + EFS/RDS — more moving parts, only worth it at multi-user.
  Gotcha: AWS free tier is time-limited; a small always-on instance is
  a few USD/month. Also satisfies E3's webhook requirement.

## Rejected

*(kept so we remember what we decided against, and why)*
