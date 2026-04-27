-- Migration 011: Audit log
--
-- Captures significant user actions for compliance, debugging, and
-- future admin-facing activity feeds. Intentionally NOT logging every
-- API call (use api_call_log for that) — only user-initiated actions
-- that matter for "who changed what, when."
--
-- Initial actions logged:
--   login                 — successful authentication
--   report_run            — compliance check started
--   report_cancel         — check cancelled mid-run
--   requirement_recheck   — single requirement re-checked
--   note_add              — note posted on a requirement
--   dev_note_triage       — dev note status transitioned
--   org_settings_change   — org name / status / API keys updated
--   user_invite           — user invited to an org
--   user_role_change      — user role changed by admin
--
-- Retention: rows are kept indefinitely for now; add a cron sweep if
-- the table grows too large after the first few months of usage.
--
-- Run on Railway:
--   railway run python tools/run_migration.py migrations/011_audit_log.sql
-- Safe to re-run.

CREATE TABLE IF NOT EXISTS audit_log (
    id           SERIAL PRIMARY KEY,
    user_id      INTEGER REFERENCES users(id),
    org_id       INTEGER REFERENCES organizations(id),
    action       TEXT NOT NULL,
    target_type  TEXT,                     -- 'report' | 'requirement' | 'organization' | 'user' | 'note'
    target_id    INTEGER,                  -- id of the affected row
    metadata     JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_log_user    ON audit_log(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_org     ON audit_log(org_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_action  ON audit_log(action);
CREATE INDEX IF NOT EXISTS idx_audit_log_created ON audit_log(created_at DESC);
