-- Migration 006: Notifications system
--
-- A unified queue of in-app notifications shown in the top-bar bell.
-- Each row is one notification for one user. Optional email delivery is
-- handled by the application layer at write time (tools/notifications.py)
-- — this table is only the in-app queue.
--
-- Initial triggers (more added as features land):
--   dev_note         — reviewer/admin filed a bug ticket on Solclear.
--                      Recipient: all superadmins.
--   dev_note_status  — superadmin transitioned a dev note's state
--                      (acknowledged / corrected). Recipient: original author.
--   check_complete   — a compliance check finished AND has attention items
--                      (FAIL / MISSING / ERROR / NEEDS_REVIEW).
--                      Recipient: all reviewers in the running user's org.
--   check_cancelled  — a check was cancelled mid-run.
--                      Recipient: the runner only.
--
-- The schema is deliberately permissive on `kind` (free-form TEXT, no
-- CHECK constraint) so adding new triggers doesn't require a schema
-- change. Each kind's payload conventions live in tools/notifications.py.
--
-- Run on Railway:
--   railway run python tools/run_migration.py migrations/006_notifications_table.sql
-- Safe to re-run: uses IF NOT EXISTS.

CREATE TABLE IF NOT EXISTS notifications (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    kind        TEXT NOT NULL,
    title       TEXT NOT NULL,
    body        TEXT,
    -- Relative URL the bell row should deep-link to when clicked.
    -- Always relative so prod/preview/local environments work uniformly.
    link_url    TEXT,
    -- Free-form payload for renderer extras (e.g. counts to badge,
    -- status colors, originator name). Keep small — this row is read
    -- on every bell poll.
    metadata    JSONB NOT NULL DEFAULT '{}'::jsonb,
    -- NULL = unread. Setting this to NOW() marks it read. We don't
    -- delete read notifications — they accumulate as a personal
    -- audit trail until a future retention job sweeps them.
    read_at     TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Hot path: bell poll counts unread for one user. Partial index keeps
-- it small even as read history grows.
CREATE INDEX IF NOT EXISTS idx_notifications_user_unread
    ON notifications(user_id)
    WHERE read_at IS NULL;

-- Secondary: full list ordered newest-first for the dropdown panel.
CREATE INDEX IF NOT EXISTS idx_notifications_user_created
    ON notifications(user_id, created_at DESC);
