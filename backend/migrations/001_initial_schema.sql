-- Migration 001: initial database schema.
--
-- WHAT A MIGRATION IS: a numbered, append-only SQL file describing one change
-- to the database's structure. We never edit an already-applied migration —
-- to change the schema later we add 002_xxx.sql, 003_xxx.sql, and so on.
-- The runner in app/db.py applies any files that haven't been applied yet,
-- so every copy of the database (your machine, the server, a fresh clone)
-- converges on the same structure by replaying the same steps in order.
--
-- Conventions used throughout this schema:
--   * Every table has user_id  -> the "multi-user ready" rule from
--     ARCHITECTURE.md. v1 has exactly one user (seeded below), but no query
--     or table ever assumes that.
--   * Dates/times are stored as TEXT in ISO format ("2026-07-05" /
--     "2026-07-05T12:31:00Z"). SQLite has no real date type; ISO text sorts
--     correctly alphabetically, which is all we need.
--   * REAL (floating point) for nutrition numbers — grams and kcal are not
--     always whole numbers (e.g. 12.5 g protein).


-- ---------------------------------------------------------------------------
-- users: who owns the data. v1 seeds a single row and every other table
-- points at it via user_id. When real accounts arrive (v2), this table gains
-- columns like email/password_hash — the structure is already in place.
-- ---------------------------------------------------------------------------
CREATE TABLE users (
    -- INTEGER PRIMARY KEY in SQLite = auto-incrementing unique row id
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))  -- set automatically on insert
);


-- ---------------------------------------------------------------------------
-- entries: one logged meal. The heart of the tracker (features F1/F2).
-- ---------------------------------------------------------------------------
CREATE TABLE entries (
    id            INTEGER PRIMARY KEY,
    -- REFERENCES = foreign key: this value must be an existing users.id.
    user_id       INTEGER NOT NULL REFERENCES users(id),

    description   TEXT NOT NULL,     -- human-readable summary, e.g. "chicken rice, large"
    calories      REAL NOT NULL,
    protein_g     REAL NOT NULL,
    carbs_g       REAL NOT NULL,
    fat_g         REAL NOT NULL,

    -- TWO time columns, by design (see ARCHITECTURE.md "day boundary"):
    -- logged_at_utc: the exact moment, in UTC — unambiguous, good for ordering.
    -- local_date:    the calendar day THE USER experienced, captured by the
    --                browser at logging time ("2026-07-05"). Daily totals
    --                group by this, so a 23:30 supper stays on the right day
    --                even if servers/timezones would disagree.
    logged_at_utc TEXT NOT NULL,
    local_date    TEXT NOT NULL,

    -- Where the numbers came from: 'manual' (typed by user) or 'ai'
    -- (estimated from photo/text, then user-confirmed). Lets us analyze
    -- estimate quality later. CHECK = database rejects any other value.
    source        TEXT NOT NULL DEFAULT 'manual' CHECK (source IN ('manual', 'ai')),

    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Index: a lookup structure so "all entries for user X on date Y" (the
-- tracker's most common query) doesn't scan the whole table. Matters little
-- at 10 rows, a lot at 10,000.
CREATE INDEX idx_entries_user_local_date ON entries (user_id, local_date);


-- ---------------------------------------------------------------------------
-- goals: calorie/macro targets. APPEND-ONLY — rows are never updated or
-- deleted. Saving a "new goal" inserts a new row with a later effective_from.
-- The goal active on any given day = the row with the newest effective_from
-- that is <= that day. This is how past days stay judged against the targets
-- that were active at the time (spec F3).
-- ---------------------------------------------------------------------------
CREATE TABLE goals (
    id                INTEGER PRIMARY KEY,
    user_id           INTEGER NOT NULL REFERENCES users(id),

    calories_target   REAL NOT NULL,
    protein_g_target  REAL NOT NULL,
    carbs_g_target    REAL NOT NULL,
    fat_g_target      REAL NOT NULL,

    -- First local date this goal applies to (inclusive), e.g. "2026-07-05".
    effective_from    TEXT NOT NULL,

    created_at        TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_goals_user_effective ON goals (user_id, effective_from);


-- ---------------------------------------------------------------------------
-- weights: body-weight log (feature F4). Simple date -> kg pairs.
-- ---------------------------------------------------------------------------
CREATE TABLE weights (
    id          INTEGER PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id),
    weight_kg   REAL NOT NULL,
    local_date  TEXT NOT NULL,   -- the day the weight was taken
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_weights_user_local_date ON weights (user_id, local_date);


-- ---------------------------------------------------------------------------
-- Seed data: the single v1 user. Every API handler will (for now) look up
-- this one user instead of reading an auth token — that lookup is the "empty
-- slot" where authentication plugs in later.
-- ---------------------------------------------------------------------------
INSERT INTO users (name) VALUES ('Mike');
