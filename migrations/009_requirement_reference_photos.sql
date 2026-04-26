-- Migration 009: Palmetto reference photos per requirement
--
-- Stores example photos scraped from Palmetto's published M1 spec page.
-- Each photo is associated with a requirement code (e.g. R1, E2) based
-- on which section of the article it appears in. Photos are mirrored
-- locally so they survive CDN rotation on Palmetto's side.
--
-- Populated by: python -m tools.run_palmetto_check (the daily cron also
-- refreshes photos whenever the spec page content changes).
--
-- Used for:
--   1. "See Palmetto reference" expandable in the report detail UI —
--      reviewers/crew can see what a passing photo looks like.
--   2. (Future) Few-shot AI prompting — include the reference photo
--      alongside the candidate to improve selection accuracy.
--
-- Run on Railway:
--   railway run python tools/run_migration.py migrations/009_requirement_reference_photos.sql
-- Safe to re-run: uses IF NOT EXISTS.

CREATE TABLE IF NOT EXISTS requirement_reference_photos (
    id              SERIAL PRIMARY KEY,
    requirement_code TEXT NOT NULL,          -- e.g. 'R1', 'E2', 'PS4'
    image_bytes      BYTEA NOT NULL,          -- mirrored from Palmetto's CDN
    mime_type        TEXT NOT NULL DEFAULT 'image/jpeg',
    src_url          TEXT NOT NULL,           -- original URL (for attribution / debugging)
    alt_text         TEXT,
    display_order    INTEGER NOT NULL DEFAULT 0,  -- ordering within a requirement
    scraped_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ref_photos_req ON requirement_reference_photos(requirement_code, display_order);
