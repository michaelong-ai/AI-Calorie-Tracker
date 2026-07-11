"""Trends API — weekly intake averages + weight series (feature F4, task T4.3).

Powers the History screen's charts AND the HTML report export (T5.1), so the
weekly-bucketing logic lives here once rather than being duplicated in the
frontend and the report generator.

Two things come back together:
  - weekly average daily calories/macros (how much I ate, smoothed to a week
    so day-to-day noise doesn't drown the trend)
  - the raw body-weight readings (did the plan move the needle?)

The frontend plots them as two stacked charts sharing a time axis — never a
dual-axis chart (two y-scales on one plot is a readability trap).
"""

from datetime import date, datetime, timedelta

from fastapi import APIRouter
from pydantic import BaseModel

from app.auth import get_current_user_id
from app.db import get_connection

router = APIRouter(prefix="/trends", tags=["trends"])


class WeekBucket(BaseModel):
    """One ISO week's averaged intake."""

    week_start: str  # Monday of the week, "YYYY-MM-DD"
    days_logged: int  # how many days that week had at least one entry
    # Averages are per LOGGED day (sum over the week / days_logged), so a
    # week where you only logged 3 days isn't unfairly shown as low.
    avg_calories: float
    avg_protein_g: float
    avg_carbs_g: float
    avg_fat_g: float


class WeightPoint(BaseModel):
    local_date: str
    weight_kg: float


class Trends(BaseModel):
    weeks: list[WeekBucket]  # oldest first — natural left-to-right time axis
    weights: list[WeightPoint]  # oldest first


def _monday_of(d: date) -> date:
    """Return the Monday on or before `d`.

    weekday() is 0 for Monday … 6 for Sunday, so subtracting that many days
    always lands on the week's Monday — our bucket key.
    """
    return d - timedelta(days=d.weekday())


@router.get("")
def trends(weeks: int = 8) -> Trends:
    """Weekly intake averages + weight readings for the last `weeks` weeks.

    `weeks` (query param, default 8) bounds how far back to look. Returns
    buckets oldest-first so the frontend can plot left-to-right without
    re-sorting.
    """
    user_id = get_current_user_id()
    # The window starts on the Monday `weeks` weeks before this week's Monday.
    today = datetime.now().date()
    window_start = _monday_of(today) - timedelta(weeks=weeks - 1)
    window_start_str = window_start.isoformat()

    conn = get_connection()
    try:
        # Per-day totals across the window (same shape as the /days query).
        day_rows = conn.execute(
            "SELECT local_date, SUM(calories) AS calories, "
            "SUM(protein_g) AS protein_g, SUM(carbs_g) AS carbs_g, "
            "SUM(fat_g) AS fat_g "
            "FROM entries WHERE user_id = ? AND local_date >= ? "
            "GROUP BY local_date",
            (user_id, window_start_str),
        ).fetchall()

        weight_rows = conn.execute(
            "SELECT local_date, weight_kg FROM weights "
            "WHERE user_id = ? AND local_date >= ? "
            "ORDER BY local_date, id",
            (user_id, window_start_str),
        ).fetchall()
    finally:
        conn.close()

    # Bucket each logged day into its week. A dict keyed by the week's Monday
    # accumulates running sums + a day count, which we average at the end.
    buckets: dict[str, dict] = {}
    for row in day_rows:
        day = date.fromisoformat(row["local_date"])
        key = _monday_of(day).isoformat()
        b = buckets.setdefault(
            key,
            {"days": 0, "calories": 0.0, "protein_g": 0.0, "carbs_g": 0.0, "fat_g": 0.0},
        )
        b["days"] += 1
        b["calories"] += row["calories"]
        b["protein_g"] += row["protein_g"]
        b["carbs_g"] += row["carbs_g"]
        b["fat_g"] += row["fat_g"]

    # Emit a bucket for EVERY week in the window (even empty ones) so the
    # chart's x-axis is continuous — a skipped week would distort the trend.
    week_list: list[WeekBucket] = []
    for i in range(weeks):
        wk = (window_start + timedelta(weeks=i)).isoformat()
        b = buckets.get(wk)
        if b and b["days"] > 0:
            n = b["days"]
            week_list.append(
                WeekBucket(
                    week_start=wk,
                    days_logged=n,
                    avg_calories=round(b["calories"] / n, 1),
                    avg_protein_g=round(b["protein_g"] / n, 1),
                    avg_carbs_g=round(b["carbs_g"] / n, 1),
                    avg_fat_g=round(b["fat_g"] / n, 1),
                )
            )
        else:
            # No data this week — zeros with days_logged=0 lets the UI render
            # a gap rather than a misleading zero-calorie bar.
            week_list.append(
                WeekBucket(
                    week_start=wk, days_logged=0, avg_calories=0,
                    avg_protein_g=0, avg_carbs_g=0, avg_fat_g=0,
                )
            )

    weights = [
        WeightPoint(local_date=r["local_date"], weight_kg=r["weight_kg"])
        for r in weight_rows
    ]
    return Trends(weeks=week_list, weights=weights)
