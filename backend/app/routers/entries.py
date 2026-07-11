"""Entries API — create, read, update, delete logged meals.

This is the single write path into the tracker. The manual-entry form (T1.2)
calls it directly, and the AI wizard's confirm step (T3.3) will call the very
same POST endpoint — by design, so there is exactly one piece of code that
can put nutrition data in the database (see ARCHITECTURE.md).

How FastAPI turns these functions into an API: the @router decorators map an
HTTP verb + URL to a function. Pydantic models declare what the request body
must look like — FastAPI validates incoming JSON against them and rejects bad
requests with a clear error before our code even runs. All endpoints appear
in the interactive docs at /docs, where they can be tried out by hand.
"""

import logging
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.auth import get_current_user_id
from app.db import get_connection

# Module-level logger; the name shows up in every log line (task D2).
logger = logging.getLogger(__name__)

# All routes in this file share the /entries prefix. tags= groups them
# under one heading in the /docs page.
router = APIRouter(prefix="/entries", tags=["entries"])


# --- Request/response shapes (Pydantic models) --------------------------------


class EntryInput(BaseModel):
    #Define using class BaseModel to ensure pydantic 
    """What the client sends to create or fully update an entry.

    Field(...) adds validation rules on top of the type: ge=0 means
    "greater than or equal to 0" — the API refuses negative calories before
    the database ever sees them. pattern= enforces the YYYY-MM-DD shape of
    local_date (the client-captured calendar day; see ARCHITECTURE.md).
    """

    description: str = Field(min_length=1, max_length=500)
    calories: float = Field(ge=0)
    protein_g: float = Field(ge=0)
    carbs_g: float = Field(ge=0)
    fat_g: float = Field(ge=0)
    local_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    # Where the numbers came from. The manual form omits this (defaults to
    # 'manual'); the AI wizard sends 'ai' or 'label' on confirm (Sprint 3).
    # Literal = only these exact strings pass validation.
    source: Literal["manual", "ai", "label"] = "manual"


class Entry(EntryInput):
    """A stored entry as the API returns it: the input fields plus what the
    server filled in (id, exact UTC time)."""

    id: int
    logged_at_utc: str


# --- Endpoints -----------------------------------------------------------------


@router.get("")
def list_entries(local_date: str) -> list[Entry]:
    """List all entries for one calendar day, oldest first.

    `local_date` arrives as a query parameter (GET /entries?local_date=...)
    because it appears in the function signature but not in the URL path.
    Returns a possibly-empty list for the current user and that day.
    """
    conn = get_connection()
    try:
        rows = conn.execute(
            # "?" placeholders let SQLite insert the values safely —
            # never build SQL by string concatenation (SQL injection).
            "SELECT * FROM entries WHERE user_id = ? AND local_date = ? "
            "ORDER BY logged_at_utc",
            (get_current_user_id(), local_date),
        ).fetchall()
        # Convert sqlite3.Row objects to dicts; FastAPI then serializes
        # them as JSON and checks they match the Entry model.
        return [Entry(**dict(row)) for row in rows]
    finally:
        conn.close()


@router.post("", status_code=201)  # 201 = "Created", the right code for POST
def create_entry(payload: EntryInput) -> Entry:
    #You Match this by defining the pydantic class EntryInput above and putting that as the request variable)
    """Log a new meal. Body must match EntryInput; returns the stored entry.

    The server (not the client) decides `logged_at_utc` — one clock, no
    trust issues — while `local_date` comes from the client, because only
    the phone knows what calendar day the user is experiencing.
    """
    # isoformat with timezone.utc produces e.g. "2026-07-05T12:31:00+00:00".
    now_utc = datetime.now(timezone.utc).isoformat(timespec="seconds")

    conn = get_connection()
    try:
        cursor = conn.execute(
            "INSERT INTO entries (user_id, description, calories, protein_g, "
            "carbs_g, fat_g, logged_at_utc, local_date, source) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                get_current_user_id(),
                payload.description,
                payload.calories,
                payload.protein_g,
                payload.carbs_g,
                payload.fat_g,
                now_utc,
                payload.local_date,
                payload.source,  # 'manual' unless the AI wizard says otherwise
            ),
        )
        conn.commit()
        # lastrowid = the id SQLite just assigned; echo the full entry back
        # so the frontend can add it to the list without a second request.
        row = conn.execute(
            "SELECT * FROM entries WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
        # App-event log (D2): the business event, not just the HTTP line.
        logger.info(
            "Entry created: id=%s source=%s kcal=%s date=%s",
            row["id"], payload.source, payload.calories, payload.local_date,
        )
        return Entry(**dict(row))
    finally:
        conn.close()


@router.put("/{entry_id}")
def update_entry(entry_id: int, payload: EntryInput) -> Entry:
    """Edit an existing entry (all editable fields replaced at once).

    `entry_id` comes from the URL path ({entry_id} in the decorator).
    Returns the updated entry, or 404 if it doesn't exist / isn't yours.
    """
    conn = get_connection()
    try:
        cursor = conn.execute(
            # The "AND user_id = ?" matters: even with one user today, no
            # query in this codebase may touch rows across users (see
            # CLAUDE.md design rules).
            "UPDATE entries SET description = ?, calories = ?, protein_g = ?, "
            "carbs_g = ?, fat_g = ?, local_date = ? "
            "WHERE id = ? AND user_id = ?",
            (
                payload.description,
                payload.calories,
                payload.protein_g,
                payload.carbs_g,
                payload.fat_g,
                payload.local_date,
                entry_id,
                get_current_user_id(),
            ),
        )
        conn.commit()
        # rowcount = how many rows the UPDATE touched. 0 means no such
        # entry for this user -> tell the client with a 404, not a silent no-op.
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Entry not found")
        row = conn.execute(
            "SELECT * FROM entries WHERE id = ?", (entry_id,)
        ).fetchone()
        return Entry(**dict(row))
    finally:
        conn.close()


@router.delete("/{entry_id}", status_code=204)  # 204 = "No Content"
def delete_entry(entry_id: int) -> None:
    """Delete an entry permanently. Returns nothing on success, 404 if absent."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            "DELETE FROM entries WHERE id = ? AND user_id = ?",
            (entry_id, get_current_user_id()),
        )
        conn.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Entry not found")
    finally:
        conn.close()
