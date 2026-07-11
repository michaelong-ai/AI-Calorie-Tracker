"""Shared test setup (pytest reads this file automatically).

THE MOST IMPORTANT IDEA HERE: tests must never touch the real database.
Every test gets a brand-new, empty, temporary database file that is deleted
afterwards. That way tests can insert/delete anything without consequences,
and every test starts from the same known state — which is what makes test
results trustworthy and repeatable.

A "fixture" is pytest's mechanism for reusable setup: any test function that
names `client` as a parameter automatically receives what the fixture below
yields, with fresh setup for each test.
"""

import pytest
from fastapi.testclient import TestClient

# Import the db MODULE (not the names inside it) so we can redirect its
# DATABASE_PATH below; get_connection() reads that variable at call time.
import app.db as db
from app.main import app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """A test HTTP client wired to a fresh temporary database.

    Inputs (provided by pytest itself):
      tmp_path    — a unique temporary folder, auto-deleted after the test.
      monkeypatch — safely swaps a value for the duration of one test,
                    restoring the original afterwards.

    Yields a TestClient: it behaves like a mini-browser for the API
    (client.get/post/put/delete) but calls the app directly in memory —
    no real server or network involved.
    """
    # Point the whole app at a database file inside the temp folder.
    monkeypatch.setattr(db, "DATABASE_PATH", tmp_path / "test.sqlite3")

    # Using TestClient as a context manager runs the app's startup logic
    # (the lifespan in main.py), which runs the migrations — so the temp
    # database gets the full schema and the seeded user, exactly like a
    # real first boot.
    with TestClient(app) as test_client:
        yield test_client
    # Leaving the "with" block runs shutdown; pytest then deletes tmp_path.


# A valid entry body used by many tests. A helper (not a fixture) so each
# test can tweak just the field it cares about with {**VALID_ENTRY, ...}.
VALID_ENTRY = {
    "description": "chicken rice, large",
    "calories": 650,
    "protein_g": 32,
    "carbs_g": 78,
    "fat_g": 20,
    "local_date": "2026-07-05",
}
