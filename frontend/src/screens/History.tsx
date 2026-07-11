// History.tsx — past days vs targets (T4.2) and the body-weight log (T4.1).
//
// Layout: weight logging card on top (quick daily habit), then the last
// 14 logged days, each compared against the goal that was ACTIVE on that
// day (goal versioning — changing targets today never rewrites last week).
// Charts and weekly-average trends come next in T4.3.

import { useEffect, useState } from "react";
import {
  deleteWeight,
  fetchActiveGoal,
  fetchDaySummaries,
  fetchTrends,
  listWeights,
  logWeight,
  reportUrl,
  toLocalDate,
} from "../api";
import type { DaySummary, Goal, TrendsData, WeightEntry } from "../types";
import { BarChart, LineChart } from "../components/charts";

// How far back the day list looks. 14 days ≈ two weeks of context without
// endless scrolling; the trend charts use 8 weeks.
const DAYS_BACK = 14;
const TREND_WEEKS = 8;

/** "2026-06-30" -> "30 Jun" for compact chart axis labels. */
function shortDate(iso: string): string {
  const d = new Date(`${iso}T12:00:00`);
  return d.toLocaleDateString(undefined, { day: "numeric", month: "short" });
}

function History() {
  const [days, setDays] = useState<DaySummary[]>([]);
  const [weights, setWeights] = useState<WeightEntry[]>([]);
  const [trends, setTrends] = useState<TrendsData | null>(null);
  const [goal, setGoal] = useState<Goal | null>(null); // for the target line
  const [weightInput, setWeightInput] = useState("");
  const [error, setError] = useState<string | null>(null);

  /** (Re)load everything — also called after logging a weight so the trend
   *  chart updates immediately. */
  function loadAll() {
    const end = toLocalDate(new Date());
    const startDate = new Date();
    startDate.setDate(startDate.getDate() - DAYS_BACK);
    const start = toLocalDate(startDate);

    fetchDaySummaries(start, end).then(setDays).catch((e: Error) => setError(e.message));
    listWeights().then(setWeights).catch(() => {});
    fetchTrends(TREND_WEEKS).then(setTrends).catch(() => {});
    fetchActiveGoal(end).then(setGoal).catch(() => {});
  }

  useEffect(loadAll, []);

  /** Record today's body weight (T4.1). */
  async function saveWeight() {
    const kg = Number(weightInput);
    if (!kg || Number.isNaN(kg)) {
      setError("Weight must be a number.");
      return;
    }
    try {
      const created = await logWeight(kg, toLocalDate(new Date()));
      setWeights([created, ...weights]); // newest first
      setWeightInput("");
      setError(null);
      fetchTrends(TREND_WEEKS).then(setTrends).catch(() => {}); // refresh the chart
    } catch (e) {
      setError((e as Error).message);
    }
  }

  /** Remove a weight reading, then refresh the trend chart. */
  async function removeWeightAndRefresh(w: WeightEntry) {
    if (!window.confirm(`Delete weight ${w.weight_kg} kg on ${w.local_date}?`)) return;
    try {
      await deleteWeight(w.id);
      setWeights(weights.filter((x) => x.id !== w.id));
      fetchTrends(TREND_WEEKS).then(setTrends).catch(() => {});
    } catch (e) {
      setError((e as Error).message);
    }
  }

  /**
   * How a day compares to its calorie target, as a CSS class.
   * "within" = under or up to 5% over (a normal day), "over" = beyond that.
   * Days without a target get no judgment — the spec says show, don't score.
   */
  function adherenceClass(day: DaySummary): string {
    if (!day.target) return "";
    return day.calories <= day.target.calories_target * 1.05 ? "within" : "over";
  }

  return (
    <section className="screen">
      <h2>History</h2>

      {error && <p className="error">{error}</p>}

      {/* --- Weight log (T4.1) --- */}
      <div className="card form">
        <h3>Body weight</h3>
        <div className="weight-row">
          <input
            inputMode="decimal"
            placeholder="kg today"
            value={weightInput}
            onChange={(e) => setWeightInput(e.target.value)}
          />
          <button type="button" className="primary" onClick={saveWeight}>
            Log
          </button>
        </div>
        {weights.length > 0 && (
          <div className="weight-list">
            {/* slice(0, 5): only the recent few here; the full trend gets
                a chart in T4.3. */}
            {weights.slice(0, 5).map((w) => (
              <p key={w.id} className="muted weight-item">
                {w.local_date}: <strong>{w.weight_kg} kg</strong>
                <button type="button" className="danger" onClick={() => removeWeightAndRefresh(w)}>
                  ✕
                </button>
              </p>
            ))}
          </div>
        )}
      </div>

      {/* --- Trends: weight + intake, stacked & time-aligned (T4.3) ---
          Two separate single-axis charts sharing the same week span —
          deliberately NOT one dual-axis plot (a readability trap). */}
      {trends && (trends.weights.length >= 2 || trends.weeks.some((w) => w.days_logged > 0)) && (
        <div className="card">
          <h3>Trends ({TREND_WEEKS} weeks)</h3>

          {/* Weight trend — needs at least two readings to draw a line. */}
          {trends.weights.length >= 2 ? (
            <>
              <p className="chart-title muted">Body weight (kg)</p>
              <LineChart
                unit="kg"
                points={trends.weights.map((w) => ({
                  label: shortDate(w.local_date),
                  value: w.weight_kg,
                }))}
              />
            </>
          ) : (
            <p className="muted">Log weight on 2+ days to see a trend line.</p>
          )}

          {/* Weekly average intake — bars, with the current goal as a
              dashed reference line. */}
          <p className="chart-title muted">Avg daily calories per week</p>
          <BarChart
            target={goal?.calories_target ?? null}
            bars={trends.weeks.map((w) => ({
              label: shortDate(w.week_start),
              value: w.avg_calories,
              muted: w.days_logged === 0,
            }))}
          />
          {goal && (
            <p className="chart-legend muted">
              Dashed line = {Math.round(goal.calories_target)} kcal target
            </p>
          )}

          {/* Latest week's macro averages as a quick stat line. */}
          {(() => {
            const latest = [...trends.weeks].reverse().find((w) => w.days_logged > 0);
            return latest ? (
              <p className="muted">
                Latest week avg: {Math.round(latest.avg_calories)} kcal · P{" "}
                {Math.round(latest.avg_protein_g)}g · C {Math.round(latest.avg_carbs_g)}g · F{" "}
                {Math.round(latest.avg_fat_g)}g ({latest.days_logged} day
                {latest.days_logged === 1 ? "" : "s"} logged)
              </p>
            ) : null;
          })()}
        </div>
      )}

      {/* --- Progress report export (T5.1) ---
          A plain download link: the backend answers with
          Content-Disposition: attachment, so tapping this saves a
          self-contained .html file (opens offline, keep as a snapshot). */}
      <a className="add-button report-link" href={reportUrl(TREND_WEEKS)} download>
        📄 Download progress report ({TREND_WEEKS} weeks)
      </a>

      {/* --- Past days vs their targets (T4.2) --- */}
      <h3>Last {DAYS_BACK} days</h3>
      {days.length === 0 ? (
        <p className="muted">No logged days in this period yet.</p>
      ) : (
        days.map((day) => (
          <div className="card day-row" key={day.local_date}>
            <div className="entry-main">
              <span>
                {day.local_date}
                <span className="muted"> · {day.entry_count} entr{day.entry_count === 1 ? "y" : "ies"}</span>
              </span>
              <span className="muted">
                P {Math.round(day.protein_g)}g · C {Math.round(day.carbs_g)}g · F{" "}
                {Math.round(day.fat_g)}g
              </span>
            </div>
            {/* kcal vs the target active THAT day; plain kcal if none. */}
            <span className={`day-kcal ${adherenceClass(day)}`}>
              {Math.round(day.calories)}
              {day.target ? ` / ${Math.round(day.target.calories_target)}` : ""} kcal
            </span>
          </div>
        ))
      )}
    </section>
  );
}

export default History;
