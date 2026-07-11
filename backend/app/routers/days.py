"""Days API — per-day nutrition summaries for the History screen (F4).

One endpoint: totals per calendar day over a date range, each day paired
with the goal that was ACTIVE ON THAT DAY (the goal-versioning rule, F3).
Days from before the first goal get target: null — the frontend shows
plain totals with no comparison for those.
"""

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app.auth import get_current_user_id
from app.db import get_connection

router = APIRouter(prefix="/days", tags=["days"])


class DayTarget(BaseModel):
    """The goal numbers that applied on one specific day."""

    calories_target: float
    protein_g_target: float
    carbs_g_target: float
    fat_g_target: float


class DaySummary(BaseModel):
    """One day's consumed totals plus its applicable target (or null)."""

    local_date: str
    calories: float
    protein_g: float
    carbs_g: float
    fat_g: float
    entry_count: int
    target: Optional[DayTarget]  # null = no goal existed yet on that day


@router.get("")
def day_summaries(start: str, end: str) -> list[DaySummary]:
    """Daily totals for local_date in [start, end], newest day first.

    Only days that HAVE entries are returned — the frontend decides how to
    render gaps (days nothing was logged).

    Implementation note: we fetch all goal versions once and match each day
    in Python. With one goal row per re-calculation this stays tiny; if it
    ever grew huge, this is the spot to push the matching into SQL.
    """
    user_id = get_current_user_id()
    conn = get_connection()
    try:
        # SUM/COUNT with GROUP BY collapses each day's entries to one row.
        day_rows = conn.execute(
            "SELECT local_date, SUM(calories) AS calories, "
            "SUM(protein_g) AS protein_g, SUM(carbs_g) AS carbs_g, "
            "SUM(fat_g) AS fat_g, COUNT(*) AS entry_count "
            "FROM entries WHERE user_id = ? AND local_date BETWEEN ? AND ? "
            "GROUP BY local_date ORDER BY local_date DESC",
            (user_id, start, end),
        ).fetchall()

        # All goal versions, newest first — matched per day below.
        goal_rows = conn.execute(
            "SELECT * FROM goals WHERE user_id = ? "
            "ORDER BY effective_from DESC, id DESC",
            (user_id,),
        ).fetchall()
    finally:
        conn.close()

    summaries = []
    for day in day_rows:
        # The active goal = first (newest) version whose effective_from is
        # on or before this day. None if the day predates every goal.
        active = next(
            (g for g in goal_rows if g["effective_from"] <= day["local_date"]),
            None,
        )
        summaries.append(
            DaySummary(
                local_date=day["local_date"],
                calories=day["calories"],
                protein_g=day["protein_g"],
                carbs_g=day["carbs_g"],
                fat_g=day["fat_g"],
                entry_count=day["entry_count"],
                target=DayTarget(
                    calories_target=active["calories_target"],
                    protein_g_target=active["protein_g_target"],
                    carbs_g_target=active["carbs_g_target"],
                    fat_g_target=active["fat_g_target"],
                )
                if active
                else None,
            )
        )
    return summaries
