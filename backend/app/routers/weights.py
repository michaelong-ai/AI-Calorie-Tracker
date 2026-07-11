"""Weights API — the body-weight log (feature F4).

Deliberately simple: date + kg pairs. Weight entries use the same
client-captured local_date rule as meals (the day is the user's day).
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.auth import get_current_user_id
from app.db import get_connection

router = APIRouter(prefix="/weights", tags=["weights"])


class WeightInput(BaseModel):
    """What the client sends to log a weight."""

    weight_kg: float = Field(gt=0, le=400)
    local_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")


class Weight(WeightInput):
    """A stored weight row."""

    id: int


@router.post("", status_code=201)
def log_weight(payload: WeightInput) -> Weight:
    """Record a body weight. Logging twice on one day is allowed —
    trend views can use the day's latest reading."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            "INSERT INTO weights (user_id, weight_kg, local_date) VALUES (?, ?, ?)",
            (get_current_user_id(), payload.weight_kg, payload.local_date),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM weights WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
        return Weight(id=row["id"], weight_kg=row["weight_kg"], local_date=row["local_date"])
    finally:
        conn.close()


@router.get("")
def list_weights() -> list[Weight]:
    """All weight readings, newest first."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM weights WHERE user_id = ? "
            "ORDER BY local_date DESC, id DESC",
            (get_current_user_id(),),
        ).fetchall()
        return [
            Weight(id=r["id"], weight_kg=r["weight_kg"], local_date=r["local_date"])
            for r in rows
        ]
    finally:
        conn.close()


@router.delete("/{weight_id}", status_code=204)
def delete_weight(weight_id: int) -> None:
    """Remove a weight reading (typo fixes). 404 if it doesn't exist."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            "DELETE FROM weights WHERE id = ? AND user_id = ?",
            (weight_id, get_current_user_id()),
        )
        conn.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Weight entry not found")
    finally:
        conn.close()
