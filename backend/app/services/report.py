"""HTML progress report generator (feature F5, task T5.1).

Produces ONE self-contained HTML file: inline CSS, inline SVG charts, zero
external references. It must open from a local file with no network — so no
<link> stylesheets, no <script src>, no web fonts, no remote images (a hard
project invariant, see CLAUDE.md). Everything the browser needs is in the
string this module returns.

Why the charts are re-drawn here in Python instead of reusing charts.tsx:
the report is generated server-side and can't run React. The SVG *specs*
(thin lines, rounded bars, target reference line, the dataviz palette) match
the on-screen charts deliberately, so the report looks like the app.

Content (spec F5): weight trend, weekly intake vs targets, adherence summary,
over a chosen period.
"""

import html
from datetime import datetime

from app.services import report_charts as chart

# Palette (from the validated dataviz set). Baked in as light-mode values —
# a downloaded report is a document, printed or viewed once, so we don't do
# theme switching; light is the safe default for print.
INK = "#0b0b0b"
MUTED = "#52514e"
SURFACE = "#fcfcfb"
PAGE = "#f9f9f7"
BORDER = "rgba(11,11,11,0.10)"
GOOD = "#006300"
CRITICAL = "#d03b3b"


def _display_date(iso: str) -> str:
    """ISO "2026-07-12" -> "12-Jul-2026" (the app-wide display format, D5).

    Mirrors the frontend's formatDate(): ISO stays the storage/API format;
    conversion happens only at the moment of display.
    """
    return datetime.fromisoformat(iso).strftime("%d-%b-%Y")


def build_report_html(
    period_label: str,
    weeks: list,        # list[WeekBucket] from the trends service
    weights: list,      # list[WeightPoint]
    days: list,         # list[DaySummary] newest-first, for the table + adherence
    goal_calories: float | None,
) -> str:
    """Assemble the full HTML document string.

    Inputs are already-computed data objects (the router fetches them). Returns
    a complete <!doctype html>… string ready to serve as a download.
    """
    generated = datetime.now().strftime("%d-%b-%Y, %H:%M")

    # --- Summary numbers ------------------------------------------------------
    logged = [d for d in days if d.entry_count > 0]
    avg_cal = round(sum(d.calories for d in logged) / len(logged)) if logged else 0

    # Adherence = share of logged days at or under 105% of that day's target.
    judged = [d for d in logged if d.target]
    within = [d for d in judged if d.calories <= d.target.calories_target * 1.05]
    adherence = round(100 * len(within) / len(judged)) if judged else None

    # Weight change over the period (first vs last reading).
    weight_change = None
    if len(weights) >= 2:
        weight_change = round(weights[-1].weight_kg - weights[0].weight_kg, 1)

    # --- Charts (inline SVG strings) -----------------------------------------
    weight_svg = (
        chart.line_chart([(w.local_date, w.weight_kg) for w in weights], unit="kg")
        if len(weights) >= 2
        else "<p class='muted'>Not enough weight readings for a trend.</p>"
    )
    intake_svg = chart.bar_chart(
        [(w.week_start, w.avg_calories, w.days_logged == 0) for w in weeks],
        target=goal_calories,
    )

    # --- Day table rows ------------------------------------------------------
    rows = []
    for d in days:
        target_txt = f"{round(d.target.calories_target)}" if d.target else "—"
        over = d.target and d.calories > d.target.calories_target * 1.05
        color = f"color:{CRITICAL}" if over else (f"color:{GOOD}" if d.target else "")
        rows.append(
            f"<tr><td>{html.escape(_display_date(d.local_date))}</td>"
            f"<td class='num'>{round(d.calories)}</td>"
            f"<td class='num'>{target_txt}</td>"
            f"<td class='num' style='{color}'>{round(d.protein_g)}/"
            f"{round(d.carbs_g)}/{round(d.fat_g)}</td></tr>"
        )
    table_rows = "\n".join(rows) if rows else (
        "<tr><td colspan='4' class='muted'>No days logged in this period.</td></tr>"
    )

    # Stat tiles — only show the ones we have data for.
    tiles = [f"<div class='tile'><div class='big'>{avg_cal}</div>"
             f"<div class='muted'>avg kcal / logged day</div></div>"]
    if adherence is not None:
        tiles.append(f"<div class='tile'><div class='big'>{adherence}%</div>"
                     f"<div class='muted'>days within target</div></div>")
    if weight_change is not None:
        arrow = "▼" if weight_change < 0 else "▲" if weight_change > 0 else "→"
        tiles.append(f"<div class='tile'><div class='big'>{arrow} {abs(weight_change)} kg</div>"
                     f"<div class='muted'>weight change</div></div>")

    # --- The document --------------------------------------------------------
    # Everything inline; the {chart.CSS} and page CSS live in one <style>.
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Calorie Tracker — Progress Report</title>
<style>
  :root {{ color-scheme: light; }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; padding: 1.5rem;
    font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
    color: {INK}; background: {PAGE};
    max-width: 720px; margin: 0 auto;
  }}
  h1 {{ font-size: 1.4rem; margin: 0 0 0.25rem; }}
  h2 {{ font-size: 1.05rem; margin: 1.5rem 0 0.5rem; }}
  .muted {{ color: {MUTED}; }}
  .sub {{ color: {MUTED}; margin: 0 0 1.25rem; font-size: 0.9rem; }}
  .card {{
    background: {SURFACE}; border: 1px solid {BORDER};
    border-radius: 10px; padding: 1rem; margin-bottom: 1rem;
  }}
  .tiles {{ display: flex; gap: 0.75rem; flex-wrap: wrap; }}
  .tile {{ flex: 1; min-width: 120px; background: {SURFACE};
    border: 1px solid {BORDER}; border-radius: 10px; padding: 0.9rem; }}
  .tile .big {{ font-size: 1.6rem; font-weight: 700; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.9rem; }}
  th, td {{ text-align: left; padding: 0.4rem 0.5rem;
    border-bottom: 1px solid {BORDER}; }}
  th {{ color: {MUTED}; font-weight: 600; }}
  .num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  {chart.CSS}
  @media print {{ body {{ background: #fff; }} .card, .tile {{ break-inside: avoid; }} }}
</style>
</head>
<body>
  <h1>🥗 Progress Report</h1>
  <p class="sub">{html.escape(period_label)} · generated {generated}</p>

  <div class="tiles">{"".join(tiles)}</div>

  <h2>Body weight</h2>
  <div class="card">{weight_svg}</div>

  <h2>Weekly average calories</h2>
  <div class="card">{intake_svg}
    {f'<p class="muted">Dashed line = {round(goal_calories)} kcal target</p>' if goal_calories else ''}
  </div>

  <h2>Daily log</h2>
  <div class="card">
    <table>
      <thead><tr><th>Date</th><th class="num">kcal</th>
        <th class="num">target</th><th class="num">P/C/F g</th></tr></thead>
      <tbody>{table_rows}</tbody>
    </table>
  </div>

  <p class="muted" style="font-size:0.8rem;margin-top:1.5rem">
    This report is self-contained — it opens offline with no internet
    connection. Keep it as a snapshot of your progress.
  </p>
</body>
</html>"""
