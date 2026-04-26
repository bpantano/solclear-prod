-- Migration 010: Per-requirement wall-clock timing
--
-- Adds total_duration_ms to requirement_results so we can monitor which
-- requirements are consistently slow. "Total" means full wall-clock from
-- when the worker picks up the requirement to when the result is saved —
-- includes photo downloads from CompanyCam, Haiku prefilter API call,
-- Sonnet validation API call, and all overhead.
--
-- The individual Anthropic call durations are already in api_call_log.
-- Together they give: downloads = total - prefilter_call - validation_call.
--
-- Run on Railway:
--   railway run python tools/run_migration.py migrations/010_requirement_timing.sql
-- Safe to re-run.

ALTER TABLE requirement_results
    ADD COLUMN IF NOT EXISTS total_duration_ms INTEGER;
