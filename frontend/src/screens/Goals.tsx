// Goals.tsx — the TDEE calculator and goal management (task T2.2).
//
// Flow (mirrors the review-before-save principle used everywhere):
//   1. User enters stats -> "Calculate" asks the backend for suggestions.
//   2. Suggested targets appear in EDITABLE fields — the user can override
//      any number before anything is stored.
//   3. "Save as my goal" stores a NEW goal version effective from today;
//      old versions are kept so past days keep their old targets.

import { useEffect, useState } from "react";
import {
  calculateTargets,
  fetchActiveGoal,
  fetchGoalHistory,
  saveGoal,
  toLocalDate,
} from "../api";
import type { CalcResult, Goal } from "../types";

// The stats form. Strings because HTML inputs hold text (converted to
// numbers when we call the API).
const BLANK_STATS = {
  weight_kg: "",
  height_cm: "",
  age: "",
  sex: "male" as "male" | "female",
  activity_level: "moderate" as
    | "sedentary"
    | "light"
    | "moderate"
    | "active"
    | "very_active",
  rate_kg_per_week: "0",
};

// Human labels for the activity dropdown, in display order.
const ACTIVITY_OPTIONS: [string, string][] = [
  ["sedentary", "Sedentary (desk job, little exercise)"],
  ["light", "Light (exercise 1–3 days/week)"],
  ["moderate", "Moderate (exercise 3–5 days/week)"],
  ["active", "Active (hard exercise 6–7 days/week)"],
  ["very_active", "Very active (physical job + training)"],
];

function Goals() {
  const [stats, setStats] = useState(BLANK_STATS);
  // The calculator's suggestion (bmr/tdee shown as explanation)...
  const [calc, setCalc] = useState<CalcResult | null>(null);
  // ...and the EDITABLE copy of the targets the user can override.
  const [targets, setTargets] = useState({
    calories_target: "",
    protein_g_target: "",
    carbs_g_target: "",
    fat_g_target: "",
  });
  const [activeGoal, setActiveGoal] = useState<Goal | null>(null);
  const [history, setHistory] = useState<Goal[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  // Load the currently-active goal and the version history on mount.
  useEffect(() => {
    fetchActiveGoal(toLocalDate(new Date())).then(setActiveGoal).catch(() => {});
    fetchGoalHistory().then(setHistory).catch(() => {});
  }, []);

  /** Step 1 -> 2: send stats to the backend calculator. */
  async function runCalculation() {
    const input = {
      weight_kg: Number(stats.weight_kg),
      height_cm: Number(stats.height_cm),
      age: Number(stats.age),
      sex: stats.sex,
      activity_level: stats.activity_level,
      rate_kg_per_week: Number(stats.rate_kg_per_week),
    };
    if ([input.weight_kg, input.height_cm, input.age].some((n) => !n || Number.isNaN(n))) {
      setError("Weight, height and age are required numbers.");
      return;
    }
    try {
      const result = await calculateTargets(input);
      setCalc(result);
      // Pre-fill the editable target fields with the suggestions.
      setTargets({
        calories_target: String(result.calories_target),
        protein_g_target: String(result.protein_g_target),
        carbs_g_target: String(result.carbs_g_target),
        fat_g_target: String(result.fat_g_target),
      });
      setError(null);
      setSaved(false);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  /** Step 3: store the (possibly edited) targets as a new goal version. */
  async function confirmGoal() {
    const payload = {
      calories_target: Number(targets.calories_target),
      protein_g_target: Number(targets.protein_g_target),
      carbs_g_target: Number(targets.carbs_g_target),
      fat_g_target: Number(targets.fat_g_target),
      effective_from: toLocalDate(new Date()), // applies from today onward
    };
    if ([payload.calories_target, payload.protein_g_target,
         payload.carbs_g_target, payload.fat_g_target].some(Number.isNaN)) {
      setError("Targets must be numbers.");
      return;
    }
    try {
      const goal = await saveGoal(payload);
      setActiveGoal(goal);
      setHistory([goal, ...history]); // newest first, same as the backend
      setSaved(true);
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <section className="screen">
      <h2>Goals</h2>

      {/* Current goal, so the screen is useful even without recalculating */}
      {activeGoal ? (
        <div className="card totals">
          <div>
            <strong>{Math.round(activeGoal.calories_target)}</strong>
            <span className="muted"> kcal/day target</span>
          </div>
          <div className="muted">
            P {Math.round(activeGoal.protein_g_target)}g · C{" "}
            {Math.round(activeGoal.carbs_g_target)}g · F{" "}
            {Math.round(activeGoal.fat_g_target)}g
          </div>
        </div>
      ) : (
        <p className="muted">No goal set yet — calculate one below.</p>
      )}

      {/* Step 1: stats */}
      <div className="card form">
        <h3>Calculate targets</h3>
        <label>
          Weight (kg)
          <input
            inputMode="decimal"
            value={stats.weight_kg}
            onChange={(e) => setStats({ ...stats, weight_kg: e.target.value })}
          />
        </label>
        <label>
          Height (cm)
          <input
            inputMode="decimal"
            value={stats.height_cm}
            onChange={(e) => setStats({ ...stats, height_cm: e.target.value })}
          />
        </label>
        <label>
          Age
          <input
            inputMode="numeric"
            value={stats.age}
            onChange={(e) => setStats({ ...stats, age: e.target.value })}
          />
        </label>
        <label>
          Sex (for the BMR formula)
          <select
            value={stats.sex}
            onChange={(e) => setStats({ ...stats, sex: e.target.value as "male" | "female" })}
          >
            <option value="male">Male</option>
            <option value="female">Female</option>
          </select>
        </label>
        <label>
          Activity level
          <select
            value={stats.activity_level}
            onChange={(e) =>
              setStats({
                ...stats,
                activity_level: e.target.value as typeof stats.activity_level,
              })
            }
          >
            {ACTIVITY_OPTIONS.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label>
          Goal
          <select
            value={stats.rate_kg_per_week}
            onChange={(e) => setStats({ ...stats, rate_kg_per_week: e.target.value })}
          >
            <option value="-0.75">Lose 0.75 kg/week (aggressive cut)</option>
            <option value="-0.5">Lose 0.5 kg/week (steady cut)</option>
            <option value="-0.25">Lose 0.25 kg/week (slow cut)</option>
            <option value="0">Maintain weight</option>
            <option value="0.25">Gain 0.25 kg/week (lean bulk)</option>
            <option value="0.5">Gain 0.5 kg/week (bulk)</option>
          </select>
        </label>
        <div className="form-actions">
          <button type="button" className="primary" onClick={runCalculation}>
            Calculate
          </button>
        </div>
      </div>

      {error && <p className="error">{error}</p>}

      {/* Step 2+3: suggestion, editable, then confirm */}
      {calc && (
        <div className="card form">
          <h3>Suggested targets</h3>
          {/* Show the working so the numbers aren't a black box. */}
          <p className="muted">
            BMR {Math.round(calc.bmr)} kcal × activity = TDEE{" "}
            {Math.round(calc.tdee)} kcal → adjusted for your goal. Edit
            anything before saving.
          </p>
          {(
            [
              ["calories_target", "Calories (kcal/day)"],
              ["protein_g_target", "Protein (g/day)"],
              ["carbs_g_target", "Carbs (g/day)"],
              ["fat_g_target", "Fat (g/day)"],
            ] as const
          ).map(([field, label]) => (
            <label key={field}>
              {label}
              <input
                inputMode="decimal"
                value={targets[field]}
                onChange={(e) => setTargets({ ...targets, [field]: e.target.value })}
              />
            </label>
          ))}
          <div className="form-actions">
            <button type="button" className="primary" onClick={confirmGoal}>
              Save as my goal
            </button>
          </div>
          {saved && <p className="muted">Saved — active from today. ✅</p>}
        </div>
      )}

      {/* Version history — proof that goals are never overwritten */}
      {history.length > 0 && (
        <div className="card">
          <h3>Goal history</h3>
          {history.map((g) => (
            <p key={g.id} className="muted">
              From {g.effective_from}: {Math.round(g.calories_target)} kcal · P{" "}
              {Math.round(g.protein_g_target)} · C {Math.round(g.carbs_g_target)} · F{" "}
              {Math.round(g.fat_g_target)}
            </p>
          ))}
        </div>
      )}
    </section>
  );
}

export default Goals;
