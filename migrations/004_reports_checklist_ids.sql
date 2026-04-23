-- Migration 004: Persist the CompanyCam checklist IDs covered by each report
--
-- Today the legacy reports.checklist_id column is a single nullable INT and
-- has been NULL on recent runs. The compliance check actually walks ALL of
-- a project's checklists, so the right shape is an array. Storing them lets
-- the report-detail page render its "Re-run failed items" button without a
-- second CompanyCam round trip (avoids rate-limiting under concurrent users)
-- and gives us a record of exactly which checklists a report covered.
--
-- Run on Railway:
--   conda run python tools/run_migration.py migrations/004_reports_checklist_ids.sql
-- Or paste the SQL into Railway dashboard → Data → Query.
-- Safe to re-run: uses IF NOT EXISTS.

ALTER TABLE reports
    ADD COLUMN IF NOT EXISTS checklist_ids JSONB NOT NULL DEFAULT '[]'::jsonb;
