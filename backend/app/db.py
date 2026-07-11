"""Database access and migrations.

This module owns two jobs:

1. `get_connection()` — hand out correctly-configured connections to the
   SQLite database file. Every part of the app that touches the database
   goes through this one function, so the configuration (foreign keys on,
   rows addressable by column name) is guaranteed everywhere.

2. `run_migrations()` — bring the database structure up to date by applying
   any SQL files in `backend/migrations/` that haven't been applied yet.
   It runs automatically at server startup (wired in main.py), which means:
   delete the .sqlite3 file and restart -> fresh, fully-built database.
   Pull new code containing 002_xxx.sql and restart -> just that one applied.

We use Python's built-in `sqlite3` module directly (no ORM) so the SQL stays
visible — a deliberate learning-project choice recorded in ARCHITECTURE.md.
"""

import sqlite3
from pathlib import Path

# --- Paths -------------------------------------------------------------------
# __file__ is this file (backend/app/db.py); .parent.parent walks up to
# backend/. Building paths relative to the code (instead of the current
# working directory) means the app finds its files no matter where the
# server was started from.
BACKEND_DIR = Path(__file__).parent.parent
DATABASE_PATH = BACKEND_DIR / "calorie_tracker.sqlite3"   # gitignored (*.sqlite3)
MIGRATIONS_DIR = BACKEND_DIR / "migrations"


def get_connection() -> sqlite3.Connection:
    """Open a connection to the app database, configured consistently.

    Takes no input. Returns a `sqlite3.Connection` ready to use. Callers are
    responsible for closing it (use `with closing(get_connection()) as ...`
    or a try/finally) so file handles don't leak.
    """
    conn = sqlite3.connect(DATABASE_PATH)

    # By default sqlite3 returns rows as plain tuples: row[3] — fragile and
    # unreadable. Row factory lets us say row["calories"] instead.
    conn.row_factory = sqlite3.Row

    # SQLite ignores foreign-key rules unless you switch them on per
    # connection (a historical quirk). Without this, inserting an entry with
    # a nonexistent user_id would silently succeed — exactly the kind of bad
    # data we declared REFERENCES to prevent.
    conn.execute("PRAGMA foreign_keys = ON")

    return conn


def run_migrations() -> list[str]:
    """Apply any not-yet-applied migration files, oldest first.

    Takes no input. Returns the list of filenames applied this run (empty if
    the database was already up to date) — handy for logging.

    How it knows what's been applied: a bookkeeping table
    `schema_migrations` stores the filename of every migration ever run.
    On each startup we diff "files on disk" against "rows in that table"
    and execute only the difference, in filename order (that's why files
    are numbered 001_, 002_, ...).
    """
    conn = get_connection()
    try:
        # The bookkeeping table itself. IF NOT EXISTS makes this safe to run
        # every startup — it only creates the table the very first time.
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                filename   TEXT PRIMARY KEY,
                applied_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )

        # Set of migrations already applied (e.g. {"001_initial_schema.sql"}).
        applied = {
            row["filename"]
            for row in conn.execute("SELECT filename FROM schema_migrations")
        }

        # All migration files on disk, sorted so 001 runs before 002.
        applied_now: list[str] = []
        for sql_file in sorted(MIGRATIONS_DIR.glob("*.sql")):
            if sql_file.name in applied:
                continue  # this one already ran on a previous startup

            # executescript runs the whole file (multiple statements) inside
            # an implicit transaction: either every statement in the file
            # succeeds, or none are kept. A migration can't half-apply.
            conn.executescript(sql_file.read_text(encoding="utf-8"))

            # Record it so it never runs again.
            conn.execute(
                "INSERT INTO schema_migrations (filename) VALUES (?)",
                (sql_file.name,),  # "?" placeholder = safe parameter binding
            )
            conn.commit()
            applied_now.append(sql_file.name)

        return applied_now
    finally:
        # Always close, even if a migration failed halfway through the loop.
        conn.close()
