-- Migration 015: track whether a requirement result used manually selected
-- photos (reviewer chose specific photos rather than letting the AI pick).
ALTER TABLE requirement_results
  ADD COLUMN IF NOT EXISTS manually_verified BOOLEAN NOT NULL DEFAULT FALSE;
