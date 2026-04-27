-- Migration 008: Photo cache on projects table
--
-- Moves the ephemeral .tmp/photos_{project_id}.json file into Postgres
-- so the photo set survives Railway redeploys. Without this, any redeploy
-- wipes the photo cache and a subsequent recheck fails with FileNotFoundError
-- (mitigated by auto-refetch in the recheck endpoint, but that adds latency
-- and a CompanyCam API round-trip every time).
--
-- Strategy:
--   - New full check: always fetch fresh from CompanyCam, save to this column
--   - Recheck:        use cached photos first, fall back to CompanyCam fetch
--   - TTL:            no hard expiry — photos are refreshed on each new check
--
-- Run on Railway:
--   railway run python tools/run_migration.py migrations/008_project_photos_cache.sql
-- Safe to re-run: uses IF NOT EXISTS / IF EXISTS.

ALTER TABLE projects
    ADD COLUMN IF NOT EXISTS photos_cache     JSONB        DEFAULT NULL,
    ADD COLUMN IF NOT EXISTS photos_cached_at TIMESTAMPTZ  DEFAULT NULL;
