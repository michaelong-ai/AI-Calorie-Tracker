"""Inline-SVG chart drawing for the HTML report (task T5.1).

This is the Python twin of the frontend's `components/charts.tsx` — same
visual specs (2px line, rounded bar tops, recessive gridlines, dashed target
line, the validated dataviz palette), rewritten here because the report is
generated server-side where React can't run. If you change how a chart looks,
change BOTH files or the report stops matching the app.

Each function returns an ``<svg>…</svg>`` string ready to drop into the
report HTML. No external libraries — the whole point of the report is zero
dependencies at view time.
"""

# Fixed drawing box; the SVG scales to its container via viewBox.
W, H = 640, 200
PAD_TOP, PAD_RIGHT, PAD_BOTTOM, PAD_LEFT = 16, 12, 26, 46

# Light-mode palette values (the report is a light-mode document — see
# report.py). Same hex as the frontend's CSS variables.
SERIES = "#2a78d6"     # blue, categorical slot 1
GRID = "#e1e0d9"
AXIS = "#898781"
TARGET = "#d03b3b"     # status: critical — the goal reference line
BAR_MUTED = "#e1e0d9"  # empty-week placeholder
INK = "#0b0b0b"

# CSS the report's <style> block includes so the SVG classes below resolve.
CSS = """
  .chart { width: 100%; height: auto; display: block; }
  .chart-grid { stroke: #e1e0d9; stroke-width: 1; }
  .chart-axis-label { fill: #898781; font-size: 11px; }
  .chart-line { stroke: #2a78d6; stroke-width: 2; stroke-linejoin: round; fill: none; }
  .chart-dot { fill: #2a78d6; }
  .chart-bar { fill: #2a78d6; }
  .chart-bar-muted { fill: #e1e0d9; }
  .chart-value { fill: #0b0b0b; font-size: 12px; font-weight: 600; }
  .chart-target { stroke: #d03b3b; stroke-width: 1.5; stroke-dasharray: 5 4; }
"""


def _y(value: float, lo: float, hi: float) -> float:
    """Map a data value to a y coordinate (inverted: bigger = higher up)."""
    plot_h = H - PAD_TOP - PAD_BOTTOM
    if hi == lo:
        return PAD_TOP + plot_h / 2
    return PAD_TOP + plot_h * (1 - (value - lo) / (hi - lo))


def _x(i: int, n: int) -> float:
    """Evenly space n marks across the plot width; x for index i."""
    plot_w = W - PAD_LEFT - PAD_RIGHT
    if n <= 1:
        return PAD_LEFT + plot_w / 2
    return PAD_LEFT + plot_w * i / (n - 1)


def _short(iso: str) -> str:
    """'2026-07-06' -> '6/7' — compact day/month for axis labels."""
    _, m, d = iso.split("-")
    return f"{int(d)}/{int(m)}"


def _gridlines(lo: float, hi: float) -> list[str]:
    """Three horizontal gridlines with y-axis value labels."""
    parts = []
    for f in (0.0, 0.5, 1.0):
        y = PAD_TOP + (H - PAD_TOP - PAD_BOTTOM) * f
        v = hi - (hi - lo) * f
        parts.append(f'<line x1="{PAD_LEFT}" y1="{y:.1f}" x2="{W - PAD_RIGHT}" '
                     f'y2="{y:.1f}" class="chart-grid"/>')
        parts.append(f'<text x="{PAD_LEFT - 6}" y="{y + 4:.1f}" class="chart-axis-label" '
                     f'text-anchor="end">{round(v)}</text>')
    return parts


def line_chart(points: list[tuple[str, float]], unit: str) -> str:
    """Single-series line chart (the weight trend).

    `points` is [(iso_date, value), …] oldest first; needs >= 2 points
    (the caller shows a message otherwise). Returns an <svg> string.
    """
    values = [v for _, v in points]
    span = (max(values) - min(values)) or 1
    lo, hi = min(values) - span * 0.1, max(values) + span * 0.1
    n = len(points)

    parts = _gridlines(lo, hi)

    # The polyline through every reading.
    coords = " ".join(f"{_x(i, n):.1f},{_y(v, lo, hi):.1f}" for i, (_, v) in enumerate(points))
    parts.append(f'<polyline points="{coords}" class="chart-line"/>')

    # Dots on every reading; the latest is bigger and direct-labelled.
    for i, (_, v) in enumerate(points):
        r = 5 if i == n - 1 else 3
        parts.append(f'<circle cx="{_x(i, n):.1f}" cy="{_y(v, lo, hi):.1f}" r="{r}" class="chart-dot"/>')
    last_date, last_v = points[-1]
    parts.append(f'<text x="{W - PAD_RIGHT}" y="{_y(last_v, lo, hi) - 9:.1f}" '
                 f'class="chart-value" text-anchor="end">{last_v} {unit}</text>')

    # First/last x labels only (labelling every point collides).
    parts.append(f'<text x="{PAD_LEFT}" y="{H - 8}" class="chart-axis-label">{_short(points[0][0])}</text>')
    parts.append(f'<text x="{W - PAD_RIGHT}" y="{H - 8}" class="chart-axis-label" '
                 f'text-anchor="end">{_short(last_date)}</text>')

    return (f'<svg viewBox="0 0 {W} {H}" class="chart" role="img" '
            f'aria-label="Weight trend, {n} readings">' + "".join(parts) + "</svg>")


def bar_chart(bars: list[tuple[str, float, bool]], target: float | None) -> str:
    """Single-series bar chart (weekly average calories).

    `bars` is [(iso_week_start, value, is_empty), …] oldest first; empty
    weeks render as faint placeholders so gaps read as gaps. `target` draws
    a dashed reference line (the calorie goal). Returns an <svg> string.
    """
    values = [v for _, v, _ in bars]
    hi = max(values + ([target] if target else []) + [1]) * 1.1
    n = len(bars)
    plot_w = W - PAD_LEFT - PAD_RIGHT
    slot = plot_w / n
    bar_w = slot * 0.6
    base_y = _y(0, 0, hi)

    parts = _gridlines(0, hi)

    for i, (_, v, empty) in enumerate(bars):
        x = PAD_LEFT + slot * i + (slot - bar_w) / 2
        y = _y(v, 0, hi)
        cls = "chart-bar-muted" if empty else "chart-bar"
        # Empty weeks get a sliver of placeholder so the axis stays readable.
        height = max(base_y - y, 2 if empty else 0)
        y_draw = base_y - height
        parts.append(f'<rect x="{x:.1f}" y="{y_draw:.1f}" width="{bar_w:.1f}" '
                     f'height="{height:.1f}" rx="3" class="{cls}"/>')

    if target and target > 0:
        ty = _y(target, 0, hi)
        parts.append(f'<line x1="{PAD_LEFT}" y1="{ty:.1f}" x2="{W - PAD_RIGHT}" '
                     f'y2="{ty:.1f}" class="chart-target"/>')

    parts.append(f'<text x="{PAD_LEFT}" y="{H - 8}" class="chart-axis-label">{_short(bars[0][0])}</text>')
    parts.append(f'<text x="{W - PAD_RIGHT}" y="{H - 8}" class="chart-axis-label" '
                 f'text-anchor="end">{_short(bars[-1][0])}</text>')

    return (f'<svg viewBox="0 0 {W} {H}" class="chart" role="img" '
            f'aria-label="Weekly average calories, {n} weeks">' + "".join(parts) + "</svg>")
