// types.ts — TypeScript definitions shared across the frontend.
//
// These mirror the JSON shapes the backend API sends and receives. Keeping
// them in one file means every screen agrees on what an "Entry" looks like,
// and the compiler catches typos like `entry.calroies` before the browser
// ever runs the code.

// One logged meal, exactly as the backend returns it (see backend
// app/routers/entries.py). Field names match the database columns.
export interface Entry {
  id: number;
  description: string;
  calories: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
  logged_at_utc: string; // e.g. "2026-07-05T12:31:00+00:00"
  local_date: string;    // e.g. "2026-07-05" — the day the user experienced
  source: "manual" | "ai";
}

// What the frontend sends when creating or editing an entry. It's the Entry
// minus the fields the backend decides itself (id, timestamps).
export interface EntryInput {
  description: string;
  calories: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
  local_date: string;
  // Optional: where the numbers came from. Omitted = 'manual';
  // the AI wizard sends 'ai' or 'label' when saving its result.
  source?: "manual" | "ai" | "label";
}

// --- AI estimation (Sprint 3) ---------------------------------------------------

// What POST /estimate returns (see backend services/estimation.py).
export interface EstimateResult {
  // estimate = judged by eye from food; label = transcribed from a
  // nutrition facts panel; unknown = AI couldn't identify food at all.
  kind: "estimate" | "label" | "unknown";
  description: string;
  assumptions: string[]; // the AI's visible working — shown on the card
  calories: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
  // For label scans: what the printed numbers refer to, so the wizard
  // can ask "how much did you have?" and scale.
  label_basis: { per: "100g" | "serving" | "package"; serving_size_g: number | null } | null;
  confidence: "low" | "medium" | "high";
}

// Summed nutrition for a set of entries — used by the daily totals bar.
export interface Totals {
  calories: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
}

// --- Goals (Sprint 2) ----------------------------------------------------------

// The user's stats as sent to the TDEE calculator (POST /goals/calculate).
export interface CalcInput {
  weight_kg: number;
  height_cm: number;
  age: number;
  sex: "male" | "female";
  activity_level: "sedentary" | "light" | "moderate" | "active" | "very_active";
  rate_kg_per_week: number; // negative = lose, 0 = maintain, positive = gain
}

// What the calculator answers: targets plus the intermediate numbers
// (bmr/tdee) so the UI can show the user how it got there.
export interface CalcResult {
  bmr: number;
  tdee: number;
  calories_target: number;
  protein_g_target: number;
  carbs_g_target: number;
  fat_g_target: number;
}

// A goal to save (POST /goals) — possibly hand-edited after calculation.
export interface GoalInput {
  calories_target: number;
  protein_g_target: number;
  carbs_g_target: number;
  fat_g_target: number;
  effective_from: string; // first local date this goal applies to
}

// A stored goal version as the backend returns it.
export interface Goal extends GoalInput {
  id: number;
}

// --- Weights & history (Sprint 4) ------------------------------------------------

// One body-weight reading.
export interface WeightEntry {
  id: number;
  weight_kg: number;
  local_date: string;
}

// --- Trends (T4.3) --------------------------------------------------------------

// One ISO week's averaged intake (see backend routers/trends.py).
export interface WeekBucket {
  week_start: string; // Monday, "YYYY-MM-DD"
  days_logged: number; // 0 = no data that week (render a gap)
  avg_calories: number;
  avg_protein_g: number;
  avg_carbs_g: number;
  avg_fat_g: number;
}

export interface WeightPoint {
  local_date: string;
  weight_kg: number;
}

export interface TrendsData {
  weeks: WeekBucket[]; // oldest first
  weights: WeightPoint[]; // oldest first
}

// One past day's totals + the target that applied that day (null = the day
// predates the first goal, so no comparison is shown).
export interface DaySummary {
  local_date: string;
  calories: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
  entry_count: number;
  target: {
    calories_target: number;
    protein_g_target: number;
    carbs_g_target: number;
    fat_g_target: number;
  } | null;
}
