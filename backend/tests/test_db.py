"""Tests for the database layer: migrations and seed data.

Each test function name describes the behavior it locks in. If someone
accidentally breaks that behavior later, the matching test fails and names
the broken promise — that's what unit tests are for.
"""

import app.db as db


def test_migrations_build_schema_from_empty(client):
    """A fresh database ends up with all five tables after startup."""
    conn = db.get_connection()
    try:
        tables = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
    finally:
        conn.close()
    # <= means "is a subset": these tables must all exist.
    assert {"users", "entries", "goals", "weights", "schema_migrations"} <= tables


def test_single_user_is_seeded(client):
    """Migration 001 creates exactly one user — the v1 'current user'."""
    conn = db.get_connection()
    try:
        users = conn.execute("SELECT * FROM users").fetchall()
    finally:
        conn.close()
    assert len(users) == 1
    assert users[0]["id"] == 1


def test_running_migrations_twice_applies_nothing(client):
    """Migrations are idempotent: a second run must be a no-op, not a crash
    (this is what lets us run them safely on every single startup)."""
    assert db.run_migrations() == []
