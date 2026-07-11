// charts.tsx — tiny dependency-free inline-SVG charts (task T4.3).
//
// WHY HAND-ROLLED SVG (no chart library): the HTML report (T5.1) must be a
// single self-contained file that opens offline with zero external
// references. A charting library pulls in scripts/fonts we'd have to inline;
// plain SVG we control renders anywhere, including inside that report.
//
// Design follows the dataviz method:
//   - colors come from CSS variables (defined in index.css), so light/dark
//     themes swap in one place and the same markup works in the report
//   - thin marks, 2px lines, rounded bar tops, recessive gridlines
//   - single-series charts need no legend (the title names the series)
//   - NEVER a dual-axis chart: weight and intake are separate charts that
//     share a time axis, not two y-scales on one plot

// Shared drawing box. A fixed viewBox with preserveAspectRatio lets one SVG
// scale to any container width (phone or report) without distortion.
const W = 320; // viewBox width — arbitrary units, not pixels
const H = 130; // viewBox height
const PAD = { top: 12, right: 8, bottom: 20, left: 34 }; // room for axis labels

/** Map a value in [min,max] to a y pixel (inverted: high value = low y). */
function yScale(v: number, min: number, max: number): number {
  const plotH = H - PAD.top - PAD.bottom;
  if (max === min) return PAD.top + plotH / 2; // flat data → centre line
  return PAD.top + plotH * (1 - (v - min) / (max - min));
}

/** Evenly space N marks across the plot width; returns the x for index i. */
function xAt(i: number, n: number): number {
  const plotW = W - PAD.left - PAD.right;
  if (n <= 1) return PAD.left + plotW / 2;
  return PAD.left + (plotW * i) / (n - 1);
}

// ---------------------------------------------------------------- Line chart

interface LinePoint {
  label: string; // x-axis label (date)
  value: number;
}

/**
 * A single-series line chart — used for the body-weight trend.
 *
 * Inputs: the points (oldest first), a unit for the axis, and an optional
 * fixed y-range. Returns an <svg>. Renders nothing meaningful for <2 points
 * (a line needs two ends) — the caller shows an empty state instead.
 */
export function LineChart({ points, unit }: { points: LinePoint[]; unit: string }) {
  const values = points.map((p) => p.value);
  // Pad the range by ~5% so the line doesn't touch the top/bottom edges.
  const rawMin = Math.min(...values);
  const rawMax = Math.max(...values);
  const span = rawMax - rawMin || 1;
  const min = rawMin - span * 0.1;
  const max = rawMax + span * 0.1;

  // Build the polyline path "x,y x,y …".
  const coords = points.map((p, i) => `${xAt(i, points.length)},${yScale(p.value, min, max)}`);

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="chart" role="img"
      aria-label={`Weight trend, ${points.length} readings`}>
      {/* Three recessive gridlines + their y-axis value labels. */}
      {[0, 0.5, 1].map((f) => {
        const v = min + (max - min) * (1 - f);
        const y = PAD.top + (H - PAD.top - PAD.bottom) * f;
        return (
          <g key={f}>
            <line x1={PAD.left} y1={y} x2={W - PAD.right} y2={y} className="chart-grid" />
            <text x={PAD.left - 4} y={y + 3} className="chart-axis-label" textAnchor="end">
              {Math.round(v)}
            </text>
          </g>
        );
      })}

      {/* The trend line itself (2px, series-1 blue via CSS). */}
      <polyline points={coords.join(" ")} className="chart-line" fill="none" />

      {/* End-point markers (≥8px target → r=3 in these viewBox units reads
          ~8px on a phone) so the latest reading is easy to find. */}
      {points.map((p, i) => (
        <circle key={i} cx={xAt(i, points.length)} cy={yScale(p.value, min, max)}
          r={i === points.length - 1 ? 3 : 2} className="chart-dot" />
      ))}

      {/* First and last x-labels only — labelling every point would collide
          on a phone (selective direct labels, per the method). */}
      <text x={PAD.left} y={H - 6} className="chart-axis-label" textAnchor="start">
        {points[0].label}
      </text>
      <text x={W - PAD.right} y={H - 6} className="chart-axis-label" textAnchor="end">
        {points[points.length - 1].label}
      </text>

      {/* The most recent value, direct-labelled — the number the user cares
          about most. */}
      <text x={W - PAD.right} y={yScale(points[points.length - 1].value, min, max) - 5}
        className="chart-value" textAnchor="end">
        {points[points.length - 1].value} {unit}
      </text>
    </svg>
  );
}

// ---------------------------------------------------------------- Bar chart

interface Bar {
  label: string;
  value: number;
  muted?: boolean; // true = no data that week; render a faint placeholder
}

/**
 * A single-series bar chart — used for weekly average calorie intake.
 *
 * Inputs: the bars (oldest first) and an optional target line (the calorie
 * goal) drawn across for reference. Returns an <svg>.
 */
export function BarChart({ bars, target }: { bars: Bar[]; target?: number | null }) {
  const values = bars.map((b) => b.value);
  // Bars start at zero (a bar's length must be proportional to its value);
  // include the target so its line is never off the top.
  const max = Math.max(...values, target ?? 0, 1) * 1.1;
  const plotW = W - PAD.left - PAD.right;
  const slot = plotW / bars.length;
  const barW = slot * 0.6; // leaves a >2px surface gap between bars

  const baselineY = yScale(0, 0, max);

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="chart" role="img"
      aria-label={`Weekly average calories, ${bars.length} weeks`}>
      {/* y gridlines at 0/50/100% of max. */}
      {[0, 0.5, 1].map((f) => {
        const y = PAD.top + (H - PAD.top - PAD.bottom) * f;
        return (
          <g key={f}>
            <line x1={PAD.left} y1={y} x2={W - PAD.right} y2={y} className="chart-grid" />
            <text x={PAD.left - 4} y={y + 3} className="chart-axis-label" textAnchor="end">
              {Math.round(max * (1 - f))}
            </text>
          </g>
        );
      })}

      {/* The bars. rx=2 rounds the tops (4px rounded data-ends, anchored to
          the zero baseline). Empty weeks render faint so gaps read as gaps. */}
      {bars.map((b, i) => {
        const x = PAD.left + slot * i + (slot - barW) / 2;
        const y = yScale(b.value, 0, max);
        return (
          <rect key={i} x={x} y={y} width={barW} height={Math.max(0, baselineY - y)}
            rx={2} className={b.muted ? "chart-bar-muted" : "chart-bar"} />
        );
      })}

      {/* Target reference line (the calorie goal), dashed so it reads as a
          reference not a data mark. Only drawn if a target exists. */}
      {target != null && target > 0 && (
        <line x1={PAD.left} y1={yScale(target, 0, max)} x2={W - PAD.right}
          y2={yScale(target, 0, max)} className="chart-target" />
      )}

      {/* First + last week labels only. */}
      <text x={PAD.left} y={H - 6} className="chart-axis-label" textAnchor="start">
        {bars[0].label}
      </text>
      <text x={W - PAD.right} y={H - 6} className="chart-axis-label" textAnchor="end">
        {bars[bars.length - 1].label}
      </text>
    </svg>
  );
}
