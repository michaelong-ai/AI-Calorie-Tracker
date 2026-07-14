// rings.tsx — the macro progress rings on Today (task T6.1, from idea E1).
//
// Four small SVG rings — calories, protein, carbs, fat — each filling
// toward its daily target, fitness-app style. This replaces the plain-text
// totals bar WHEN a goal exists; days without a goal keep the plain totals
// (a ring with no target has nothing to fill toward).
//
// Design notes (dataviz method):
//   - The four metrics are four IDENTITIES, so they use the first four
//     categorical palette slots in fixed order (blue/aqua/yellow/green),
//     validated for color-blind separation on this app's light AND dark
//     card surfaces. Colors live in index.css as CSS variables.
//   - Identity is never color-alone: every ring has its own text label and
//     numbers underneath (this is also the required "relief" for the two
//     light-mode slots that sit below 3:1 contrast).
//   - Over target = the arc switches to the reserved status color (the same
//     red as the chart target line) AND the text underneath says "+N over"
//     — a color-blind-safe second signal.
//   - All text wears ink tokens (--text / --muted), never the series color.

import type { Goal, Totals } from "../types";

// Ring geometry, in viewBox units (the SVG scales to its container).
const SIZE = 72; // viewBox is SIZE × SIZE
const R = 29; // ring radius — leaves room for the stroke inside the box
const STROKE = 7; // ring thickness
// Circumference — the length of the full circle. stroke-dasharray uses it
// to draw "this fraction of the circle" as an arc.
const CIRC = 2 * Math.PI * R;

interface RingProps {
  label: string; // "kcal", "Protein", …
  consumed: number;
  target: number;
  unit: string; // "" for kcal (the label already says it), "g" for macros
  colorClass: string; // s1–s4: which categorical palette slot to wear
}

/**
 * One ring: a grey full-circle track with a colored arc on top showing
 * consumed/target, the consumed number in the middle, and the label +
 * "consumed/target" line underneath.
 */
function Ring({ label, consumed, target, unit, colorClass }: RingProps) {
  // Fraction of the target consumed, capped at 1 — past 100% the ring is
  // simply full; the OVER state is signalled by color + text instead of
  // wrapping the arc around again (a second lap would be unreadable).
  const frac = target > 0 ? Math.min(consumed / target, 1) : 0;
  const over = target > 0 && consumed > target;

  return (
    <div className="ring">
      <svg viewBox={`0 0 ${SIZE} ${SIZE}`} role="img"
        aria-label={`${label}: ${Math.round(consumed)} of ${Math.round(target)}${unit}`}>
        {/* The track: the full circle in a recessive grid color, so the
            unfilled remainder is visible (you can see how far is left). */}
        <circle cx={SIZE / 2} cy={SIZE / 2} r={R} className="ring-track"
          strokeWidth={STROKE} />
        {/* The progress arc. stroke-dasharray "filled gap" paints only the
            first `frac` of the circumference; the rotate(-90°) starts the
            arc at 12 o'clock instead of SVG's default 3 o'clock. */}
        {frac > 0 && (
          <circle cx={SIZE / 2} cy={SIZE / 2} r={R}
            className={`ring-arc ${over ? "over" : colorClass}`}
            strokeWidth={STROKE}
            strokeDasharray={`${CIRC * frac} ${CIRC}`}
            strokeLinecap="round"
            transform={`rotate(-90 ${SIZE / 2} ${SIZE / 2})`} />
        )}
        {/* The consumed number, centered. Ink token, never the series color. */}
        <text x={SIZE / 2} y={SIZE / 2 + 5} textAnchor="middle" className="ring-value">
          {Math.round(consumed)}
        </text>
      </svg>
      {/* Label + target line. When over, "+N over" is the non-color signal
          that pairs with the arc turning red. */}
      <p className="ring-label">
        {label}
        <br />
        {over
          ? `+${Math.round(consumed - target)}${unit} over`
          : `${Math.round(consumed)}/${Math.round(target)}${unit}`}
      </p>
    </div>
  );
}

/**
 * The row of four rings. Takes the day's running totals and the goal that
 * governs the selected day; the caller only renders this when a goal exists.
 */
export function MacroRings({ totals, goal }: { totals: Totals; goal: Goal }) {
  return (
    <div className="rings">
      <Ring label="kcal" unit="" colorClass="s1"
        consumed={totals.calories} target={goal.calories_target} />
      <Ring label="Protein" unit="g" colorClass="s2"
        consumed={totals.protein_g} target={goal.protein_g_target} />
      <Ring label="Carbs" unit="g" colorClass="s3"
        consumed={totals.carbs_g} target={goal.carbs_g_target} />
      <Ring label="Fat" unit="g" colorClass="s4"
        consumed={totals.fat_g} target={goal.fat_g_target} />
    </div>
  );
}
