-- Migration 002: NEEDS_REVIEW status for compliance results
--
-- Adds a total_needs_review counter to the reports summary so the UI can
-- surface "N items need review" alongside passed/failed/missing totals.
--
-- The requirement_results.status column is a free-text TEXT column, so it
-- already accepts 'NEEDS_REVIEW' values without a schema change.
--
-- Run on Railway:
--   psql "$DATABASE_URL" -f migrations/002_needs_review_status.sql
-- Or via Railway dashboard → Data → Query.
-- Safe to run more than once (uses IF NOT EXISTS, default 0).

ALTER TABLE reports
  ADD COLUMN IF NOT EXISTS total_needs_review INTEGER NOT NULL DEFAULT 0;
