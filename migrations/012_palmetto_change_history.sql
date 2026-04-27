-- Migration 012: Palmetto requirements change history
--
-- Stores a log of every material change detected when the daily cron
-- (or the "Check Now" button) compares Palmetto's published M1 spec
-- against the prior snapshot. Gives the Requirements tab a scrollable
-- history box showing "what changed and when" separate from manual edits.
--
-- Non-material diffs (timestamps, layout changes) are NOT stored here —
-- only rows where the AI analysis flagged is_material = TRUE.
--
-- Run on Railway:
--   railway run python tools/run_migration.py migrations/012_palmetto_change_history.sql
-- Safe to re-run.

CREATE TABLE IF NOT EXISTS palmetto_change_history (
    id              SERIAL PRIMARY KEY,
    detected_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    summary         TEXT,                         -- AI-generated plain English summary
    lines_added     INTEGER NOT NULL DEFAULT 0,
    lines_removed   INTEGER NOT NULL DEFAULT 0,
    new_req_ids     JSONB NOT NULL DEFAULT '[]',  -- requirement codes newly found on page
    changed_req_ids JSONB NOT NULL DEFAULT '[]',  -- existing codes whose text changed
    removed_req_ids JSONB NOT NULL DEFAULT '[]'   -- codes no longer on the page
);

CREATE INDEX IF NOT EXISTS idx_palmetto_history_detected ON palmetto_change_history(detected_at DESC);
