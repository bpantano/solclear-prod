-- Migration 007: Reply threads on notes
--
-- Adds a self-referencing parent_note_id so a note can be a reply to
-- another note. Top-level note: parent_note_id IS NULL. Reply: points
-- to its parent. Replies inherit visibility from their parent at the
-- application layer (a public note's replies are public; a dev note's
-- replies are dev-visible).
--
-- Replies are immutable once posted (same convention as top-level
-- notes — see migration 005). Status (dev_status) lives on the
-- top-level note only; replies don't have triage state.
--
-- Run on Railway:
--   railway run python tools/run_migration.py migrations/007_notes_replies.sql
-- Safe to re-run.

ALTER TABLE notes
    ADD COLUMN IF NOT EXISTS parent_note_id INTEGER REFERENCES notes(id) ON DELETE CASCADE;

CREATE INDEX IF NOT EXISTS idx_notes_parent ON notes(parent_note_id)
    WHERE parent_note_id IS NOT NULL;
