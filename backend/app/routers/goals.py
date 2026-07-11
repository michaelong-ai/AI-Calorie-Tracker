"""Goals API — TDEE calculation and versioned calorie/macro targets (F3).

Two ideas live here:

1. /goals/calculate is a pure calculator: stats in, suggested targets out.
   It saves NOTHING — the user reviews/edits the suggestion in the UI first
   (same review-before-save principle as the AI estimates).

2. Saving a goal INSERTs a new row; nothing is ever updated or deleted
   (append-only, per ARCHITECTURE.md). "Which goal applies on day X?" is
   answered by picking the newest row whose effective_from is on or before
   X — so past days keep being judged by the targets that were active then.
"""

import logging
from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.auth import get_current_user_id
from app.db import get_connection
from app.services.tdee import calculate_targets

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/goals", tags=["goals"])


# --- Request/response shapes ---------------------------------------------------


class CalcInput(BaseModel):
    """The user's stats, as the calculator form sends them.

    Literal[...] means "only exactly these strings are allowed" — FastAPI
    turns anything else into a 422 validation error automatically, which is
    why the tdee service can trust its inputs.
    """

    weight_kg: float = Field(gt=0, le=400)
    height_cm: float = Field(gt=0, le=280)
    age: int = Field(gt=0, le=120)
    sex: Literal["male", "female"]
    activity_level: Literal["sedentary", "light", "moderate", "active", "very_active"]
    # Signed: negative = lose weight, 0 = maintain, positive = gain.
    # Capped at ±1 kg/week — beyond that is not a sensible target.
    rate_kg_per_week: float = Field(ge=-1, le=1)


class CalcResult(BaseModel):
    """What the calculator returns — targets plus the intermediate numbers
    (bmr, tdee) so the UI can show the user how it got there."""

    bmr: float
    tdee: float
    calories_target: float
    protein_g_target: float
    carbs_g_target: float
    fat_g_target: float


class GoalInput(BaseModel):
    """A goal as the user confirms it (possibly hand-edited targets)."""

    calories_target: float = Field(gt=0)
    protein_g_target: float = Field(ge=0)
    carbs_g_target: float = Field(ge=0)
    fat_g_target: float = Field(ge=0)
    effective_from: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")


class Goal(GoalInput):
    """A stored goal row."""

    id: int


# --- Endpoints -----------------------------------------------------------------


@router.post("/calculate")
def calculate(payload: CalcInput) -> CalcResult:
    """Compute suggested targets from stats. Pure function — writes nothing."""
    return CalcResult(**calculate_targets(**payload.model_dump()))


@router.post("", status_code=201)
def save_goal(payload: GoalInput) -> Goal:
    """Save a goal as a NEW version (append-only — never overwrites).

    Saving twice on the same effective_from is allowed; the newer row wins
    the active-goal lookup below via its higher id (created later).
    """
    conn = get_connection()
    try:
        cursor = conn.execute(
            "INSERT INTO goals (user_id, calories_target, protein_g_target, "
            "carbs_g_target, fat_g_target, effective_from) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                get_current_user_id(),
                payload.calories_target,
                payload.protein_g_target,
                payload.carbs_g_target,
                payload.fat_g_target,
                payload.effective_from,
            ),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM goals WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
        # App-event log (D2): a new goal version is a milestone worth a line.
        logger.info(
            "Goal saved: id=%s kcal=%s effective_from=%s",
            row["id"], payload.calories_target, payload.effective_from,
        )
        return _to_goal(row)
    finally:
        conn.close()


@router.get("/active")
def active_goal(local_date: Optional[str] = None) -> Optional[Goal]:
    """The goal that applies on `local_date` (default: today, UTC clock).

    Returns null (None) — not an error — when the date is before the first
    goal ever set: the spec says such days show totals without comparison,
    and the frontend uses null to decide that.
    """
    if local_date is None:
        local_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    conn = get_connection()
    try:
        # "newest effective_from that is <= the date" — ties broken by id
        # (the row created last wins).
        row = conn.execute(
            "SELECT * FROM goals WHERE user_id = ? AND effective_from <= ? "
            "ORDER BY effective_from DESC, id DESC LIMIT 1",
            (get_current_user_id(), local_date),
        ).fetchone()
        return _to_goal(row) if row else None
    finally:
        conn.close()


@router.get("")
def goal_history() -> list[Goal]:
    """All goal versions, newest first — the audit trail of targets."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM goals WHERE user_id = ? "
            "ORDER BY effective_from DESC, id DESC",
            (get_current_user_id(),),
        ).fetchall()
        return [_to_goal(row) for row in rows]
    finally:
        conn.close()


def _to_goal(row) -> Goal:
    """Convert a database row to the API's Goal shape.

    (Leading underscore = module-private helper, not an endpoint.)
    """
    return Goal(
        id=row["id"],
        calories_target=row["calories_target"],
        protein_g_target=row["protein_g_target"],
        carbs_g_target=row["carbs_g_target"],
        fat_g_target=row["fat_g_target"],
        effective_from=row["effective_from"],
    )
