-- Migration 002: allow 'label' as an entry source (feature E2, promoted into
-- Sprint 3). An entry can now come from:
--   'manual' — typed by the user
--   'ai'     — estimated by the vision model from a photo/description
--   'label'  — transcribed from a nutrition facts panel (near-exact numbers)
--
-- WHY THIS FILE IS LONGER THAN YOU'D EXPECT: SQLite cannot modify a CHECK
-- constraint in place (no ALTER TABLE ... ALTER COLUMN). The official
-- procedure is to rebuild the table: create the new version under a temp
-- name, copy the data, drop the old table, rename. The migration runner
-- wraps this whole file in one transaction, so a failure midway leaves the
-- database untouched.

CREATE TABLE entries_new (
    id            INTEGER PRIMARY KEY,
    user_id       INTEGER NOT NULL REFERENCES users(id),
    description   TEXT NOT NULL,
    calories      REAL NOT NULL,
    protein_g     REAL NOT NULL,
    carbs_g       REAL NOT NULL,
    fat_g         REAL NOT NULL,
    logged_at_utc TEXT NOT NULL,
    local_date    TEXT NOT NULL,
    -- the only change: 'label' joins the allowed values
    source        TEXT NOT NULL DEFAULT 'manual' CHECK (source IN ('manual', 'ai', 'label')),
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Copy every existing row across (column lists kept explicit so a future
-- column addition can't silently misalign the copy).
INSERT INTO entries_new (id, user_id, description, calories, protein_g,
                         carbs_g, fat_g, logged_at_utc, local_date, source,
                         created_at)
SELECT id, user_id, description, calories, protein_g,
       carbs_g, fat_g, logged_at_utc, local_date, source,
       created_at
FROM entries;

DROP TABLE entries;
ALTER TABLE entries_new RENAME TO entries;

-- Indexes are dropped with the old table — recreate them.
CREATE INDEX idx_entries_user_local_date ON entries (user_id, local_date);
