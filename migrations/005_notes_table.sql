-- Migration 005: Notes table (public + dev)
--
-- Creates a unified `notes` table supporting two kinds of notes on a
-- requirement result:
--   - public: crew/reviewer/admin comments on a requirement, visible to
--             everyone with access to the report. Immutable once posted
--             (comment-thread style: post follow-ups, don't edit history).
--   - dev:    reviewer/admin bug tickets filed against Solclear itself
--             ("this prompt is wrong", "AI misread this photo"). Visible
--             only to reviewer / admin / superadmin. Goes through a
--             triage workflow: open → acknowledged → corrected.
--
-- Replaces the single-value `requirement_results.notes` TEXT column.
-- Existing values are backfilled into this table as public notes with
-- a NULL author (the legacy column never captured who wrote the note).
-- The legacy column is left in place for now; dropping it is a separate
-- follow-up migration once we're confident the new table is working.
--
-- Run on Railway:
--   railway run python tools/run_migration.py migrations/005_notes_table.sql
--
-- Safe to re-run: uses IF NOT EXISTS. Backfill uses
-- ON CONFLICT DO NOTHING semantics (via WHERE NOT EXISTS) so re-running
-- doesn't duplicate legacy notes.

CREATE TABLE IF NOT EXISTS notes (
    id                   SERIAL PRIMARY KEY,
    report_id            INTEGER NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
    -- Nullable so a future per-report or per-project note can plug in
    -- without a schema change. Per-req-result is the only shape we
    -- support today, so new rows will always have this set.
    requirement_result_id INTEGER REFERENCES requirement_results(id) ON DELETE CASCADE,
    project_id           INTEGER REFERENCES projects(id),
    -- Nullable because legacy backfilled notes have no known author.
    author_user_id       INTEGER REFERENCES users(id),
    visibility           TEXT NOT NULL DEFAULT 'public'
                         CHECK (visibility IN ('public', 'dev')),
    body                 TEXT NOT NULL,
    -- Dev-note triage state. NULL for public notes.
    dev_status           TEXT
                         CHECK (dev_status IN ('open', 'acknowledged', 'corrected')),
    resolved_at          TIMESTAMPTZ,
    resolved_by_user_id  INTEGER REFERENCES users(id),
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_notes_report ON notes(report_id);
CREATE INDEX IF NOT EXISTS idx_notes_req_result ON notes(requirement_result_id);
CREATE INDEX IF NOT EXISTS idx_notes_author ON notes(author_user_id);
-- Partial index for the superadmin dev-notes triage tab — most queries
-- filter by status so this keeps the hot path fast without indexing
-- the public notes (which vastly outnumber dev notes).
CREATE INDEX IF NOT EXISTS idx_notes_dev_open
    ON notes(dev_status, created_at DESC)
    WHERE visibility = 'dev';

-- Backfill: copy any existing non-empty requirement_results.notes into
-- the new table as public notes. NULL author for legacy. Use NOT EXISTS
-- so re-running the migration is a no-op rather than creating duplicates.
INSERT INTO notes (report_id, requirement_result_id, author_user_id, visibility, body, created_at)
SELECT rr.report_id, rr.id, NULL, 'public', rr.notes, COALESCE(rr.resolved_at, NOW())
FROM requirement_results rr
WHERE rr.notes IS NOT NULL
  AND TRIM(rr.notes) <> ''
  AND NOT EXISTS (
      SELECT 1 FROM notes n
      WHERE n.requirement_result_id = rr.id
        AND n.visibility = 'public'
        AND n.body = rr.notes
  );
