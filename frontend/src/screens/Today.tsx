// Today.tsx — the home screen: one day's meal log.
//
// Covers three backlog tasks in one component:
//   T1.2 — chronological entry list with add / edit / delete
//   T1.3 — daily totals that update immediately on any change
//   T1.4 — navigate to previous days and edit them
//
// Data flow: this component keeps the selected date and that day's entries
// in state. Every mutation (add/edit/delete) calls the backend through
// api.ts, then updates local state with the result — so the totals bar,
// which is COMPUTED from the entries array on every render, is always
// consistent with what's on screen. No cached numbers to get stale.

import { useEffect, useState } from "react";
import {
  createEntry,
  deleteEntry,
  fetchActiveGoal,
  formatDate,
  listEntries,
  toLocalDate,
  updateEntry,
} from "../api";
import type { Entry, EntryInput, Goal, Totals } from "../types";
import Wizard from "../components/Wizard";

// The empty form used when adding a new entry. Numbers start as "" (empty
// string) because HTML inputs hold text; we convert to numbers on save.
const BLANK_FORM = {
  description: "",
  calories: "",
  protein_g: "",
  carbs_g: "",
  fat_g: "",
};
type FormValues = typeof BLANK_FORM;

function Today() {
  // --- State -----------------------------------------------------------
  // Which calendar day we're looking at (T1.4). Starts as today.
  const [date, setDate] = useState<string>(toLocalDate(new Date()));
  // The entries of the selected day, as loaded from the backend.
  const [entries, setEntries] = useState<Entry[]>([]);
  // null = form closed; "new" = adding; a number = editing that entry id.
  const [editing, setEditing] = useState<null | "new" | number>(null);
  const [form, setForm] = useState<FormValues>(BLANK_FORM);
  // Holds an error message to show the user, or null when all is well.
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  // The goal that applies to the SELECTED day (T2.3) — not necessarily
  // today's goal: viewing last week uses last week's targets (goal
  // versioning, spec F3). null = that day predates any goal, so the UI
  // shows plain totals without comparison.
  const [goal, setGoal] = useState<Goal | null>(null);
  // Whether the AI scan wizard is open (Sprint 3).
  const [scanning, setScanning] = useState(false);

  // --- Load entries whenever the selected date changes ------------------
  // [date] as the dependency list = re-run this effect when `date` changes
  // (including the first render). Navigating days is just setDate();
  // this effect does the fetching.
  useEffect(() => {
    setLoading(true);
    listEntries(date)
      .then((rows) => {
        setEntries(rows);
        setError(null);
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
    // Also fetch which goal governs this day (T2.3). Failure here is not
    // fatal — the screen just shows totals without targets.
    fetchActiveGoal(date).then(setGoal).catch(() => setGoal(null));
  }, [date]);

  // --- Totals (T1.3) -----------------------------------------------------
  // Recomputed from the entries array on every render — add/edit/delete
  // changes the array, so the totals can never disagree with the list.
  const totals: Totals = entries.reduce(
    (sum, e) => ({
      calories: sum.calories + e.calories,
      protein_g: sum.protein_g + e.protein_g,
      carbs_g: sum.carbs_g + e.carbs_g,
      fat_g: sum.fat_g + e.fat_g,
    }),
    { calories: 0, protein_g: 0, carbs_g: 0, fat_g: 0 },
  );

  // --- Day navigation (T1.4) ---------------------------------------------
  /** Shift the selected date by +1 or -1 day. */
  function shiftDay(delta: number) {
    // "T12:00:00": parse at noon so daylight-saving jumps can't slide the
    // date to the wrong day (midnight is the risky moment).
    const d = new Date(`${date}T12:00:00`);
    d.setDate(d.getDate() + delta);
    setDate(toLocalDate(d));
    setEditing(null); // close any open form when switching days
    setScanning(false); // and the scan wizard too
  }
  const isToday = date === toLocalDate(new Date());

  // --- Form helpers -------------------------------------------------------
  /** Open the form pre-filled for editing an existing entry. */
  function startEdit(entry: Entry) {
    setEditing(entry.id);
    setForm({
      description: entry.description,
      calories: String(entry.calories),
      protein_g: String(entry.protein_g),
      carbs_g: String(entry.carbs_g),
      fat_g: String(entry.fat_g),
    });
  }

  /** Open the form blank for a new entry. */
  function startAdd() {
    setEditing("new");
    setForm(BLANK_FORM);
  }

  /** Save the form — POST for a new entry, PUT when editing (T1.2). */
  async function save() {
    // Convert the text inputs to numbers; empty/invalid becomes NaN, which
    // we catch here rather than sending garbage to the API.
    const payload: EntryInput = {
      description: form.description.trim(),
      calories: Number(form.calories),
      protein_g: Number(form.protein_g),
      carbs_g: Number(form.carbs_g),
      fat_g: Number(form.fat_g),
      local_date: date, // captured client-side — the day-boundary rule
    };
    if (!payload.description) {
      setError("Description is required.");
      return;
    }
    if ([payload.calories, payload.protein_g, payload.carbs_g, payload.fat_g].some(Number.isNaN)) {
      setError("Calories and macros must be numbers (use 0 if unknown).");
      return;
    }

    try {
      if (editing === "new") {
        const created = await createEntry(payload);
        setEntries([...entries, created]); // append; list stays chronological
      } else if (typeof editing === "number") {
        const updated = await updateEntry(editing, payload);
        // Replace just the edited entry in the array, keeping order.
        setEntries(entries.map((e) => (e.id === editing ? updated : e)));
      }
      setEditing(null);
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  /** Delete an entry after a confirmation tap (T1.2). */
  async function remove(entry: Entry) {
    // window.confirm is a plain browser yes/no dialog — crude but honest;
    // a nicer in-app dialog is polish for Sprint 5.
    if (!window.confirm(`Delete "${entry.description}"?`)) return;
    try {
      await deleteEntry(entry.id);
      setEntries(entries.filter((e) => e.id !== entry.id));
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  // --- Render --------------------------------------------------------------
  return (
    <section className="screen">
      {/* Day navigation header (T1.4) */}
      <div className="day-nav">
        <button type="button" onClick={() => shiftDay(-1)} aria-label="Previous day">
          ‹
        </button>
        <h2>{isToday ? "Today" : formatDate(date)}</h2>
        {/* Can't navigate into the future — the forward arrow disappears on today. */}
        <button
          type="button"
          onClick={() => shiftDay(1)}
          aria-label="Next day"
          style={{ visibility: isToday ? "hidden" : "visible" }}
        >
          ›
        </button>
      </div>

      {/* Totals bar (T1.3 + T2.3): consumed, and — when a goal governs this
          day — what's left. Days before the first goal show totals only. */}
      <div className="card">
        <div className="totals">
          <div>
            <strong>{Math.round(totals.calories)}</strong>
            <span className="muted">
              {goal ? ` / ${Math.round(goal.calories_target)} kcal` : " kcal"}
            </span>
          </div>
          <div className="muted">
            P {Math.round(totals.protein_g)}
            {goal ? `/${Math.round(goal.protein_g_target)}` : ""}g · C{" "}
            {Math.round(totals.carbs_g)}
            {goal ? `/${Math.round(goal.carbs_g_target)}` : ""}g · F{" "}
            {Math.round(totals.fat_g)}
            {goal ? `/${Math.round(goal.fat_g_target)}` : ""}g
          </div>
        </div>
        {goal ? (
          // The "what do I have left today" line — the number the user
          // actually decides dinner by. Negative = over target.
          <p className={totals.calories > goal.calories_target ? "error" : "muted"}>
            {totals.calories <= goal.calories_target
              ? `${Math.round(goal.calories_target - totals.calories)} kcal left · ` +
                `${Math.max(0, Math.round(goal.protein_g_target - totals.protein_g))} g protein to go`
              : `${Math.round(totals.calories - goal.calories_target)} kcal over target`}
          </p>
        ) : (
          // Empty state (T5.2): no goal governs this day. Explain why there
          // is no target instead of leaving a bare number.
          !loading && (
            <p className="muted">
              No goal set for this day — use the <strong>Goals</strong> tab to
              calculate your targets.
            </p>
          )
        )}
      </div>

      {error && <p className="error">{error}</p>}

      {/* Entry list (T1.2) */}
      {loading ? (
        <p className="muted">Loading…</p>
      ) : entries.length === 0 ? (
        <p className="muted">Nothing logged on this day yet.</p>
      ) : (
        entries.map((entry) => (
          <div className="card entry" key={entry.id}>
            <div className="entry-main">
              <span>{entry.description}</span>
              <span className="muted">
                {Math.round(entry.calories)} kcal · P {Math.round(entry.protein_g)} · C{" "}
                {Math.round(entry.carbs_g)} · F {Math.round(entry.fat_g)}
              </span>
            </div>
            <div className="entry-actions">
              <button type="button" onClick={() => startEdit(entry)}>
                ✏️
              </button>
              <button type="button" className="danger" onClick={() => remove(entry)}>
                🗑️
              </button>
            </div>
          </div>
        ))
      )}

      {/* Add/edit form — rendered only while open */}
      {editing !== null ? (
        <div className="card form">
          <h3>{editing === "new" ? "Add entry" : "Edit entry"}</h3>
          <label>
            Description
            <input
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              placeholder="e.g. chicken rice, large portion"
            />
          </label>
          {/* One numeric input per nutrient. inputMode="decimal" makes
              phones show the number keypad instead of the full keyboard. */}
          {(
            [
              ["calories", "Calories (kcal)"],
              ["protein_g", "Protein (g)"],
              ["carbs_g", "Carbs (g)"],
              ["fat_g", "Fat (g)"],
            ] as const
          ).map(([field, label]) => (
            <label key={field}>
              {label}
              <input
                inputMode="decimal"
                value={form[field]}
                onChange={(e) => setForm({ ...form, [field]: e.target.value })}
                placeholder="0"
              />
            </label>
          ))}
          <div className="form-actions">
            <button type="button" onClick={() => setEditing(null)}>
              Cancel
            </button>
            <button type="button" className="primary" onClick={save}>
              Save
            </button>
          </div>
        </div>
      ) : scanning ? (
        // The AI wizard (Sprint 3). It saves through the same entries API
        // as the manual form, then hands the new entry back to this list.
        <Wizard
          date={date}
          onSaved={(entry) => setEntries([...entries, entry])}
          onClose={() => setScanning(false)}
        />
      ) : (
        // Two ways in: AI scan (primary, hence green) or manual entry.
        <div className="add-row">
          <button type="button" className="primary add-button" onClick={() => setScanning(true)}>
            📷 Scan meal
          </button>
          <button type="button" className="add-button" onClick={startAdd}>
            ＋ Add manually
          </button>
        </div>
      )}
    </section>
  );
}

export default Today;
