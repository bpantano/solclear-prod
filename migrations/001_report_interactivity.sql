-- Migration 001: Interactive report detail (resolve / note)
--
-- Adds three columns to requirement_results so users can mark items resolved,
-- leave notes, and attribute who did it. All additions are nullable — existing
-- rows keep working with NULLs.
--
-- Run on Railway:
--   psql "$DATABASE_URL" -f migrations/001_report_interactivity.sql
-- Or via Railway dashboard → Data → Query.
-- Safe to run more than once (uses IF NOT EXISTS).

ALTER TABLE requirement_results
  ADD COLUMN IF NOT EXISTS resolved_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS resolved_by INTEGER REFERENCES users(id),
  ADD COLUMN IF NOT EXISTS notes TEXT;
