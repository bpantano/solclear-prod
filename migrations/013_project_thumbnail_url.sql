-- Migration 013: cache thumbnail URL on projects so the Reports list
-- doesn't need a CompanyCam API call per row.
-- Populated by run_check_thread when photos are fetched.
ALTER TABLE projects ADD COLUMN IF NOT EXISTS thumbnail_url TEXT;
