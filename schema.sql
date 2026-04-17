-- Solclear Database Schema
-- PostgreSQL on Railway
-- Run this to initialize the database

-- ── Auto-update timestamp trigger ────────────────────────────────────────────

CREATE OR REPLACE FUNCTION update_timestamp()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ── Organizations ────────────────────────────────────────────────────────────

CREATE TABLE organizations (
    id              SERIAL PRIMARY KEY,
    name            TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'onboarding',  -- 'active', 'demo', 'inactive', 'onboarding'
    companycam_api_key TEXT,          -- encrypted in production
    anthropic_api_key TEXT,           -- per-org API key (encrypted in production)
    settings        JSONB DEFAULT '{}',  -- org-level toggles and config
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TRIGGER organizations_update_timestamp BEFORE UPDATE ON organizations
  FOR EACH ROW EXECUTE FUNCTION update_timestamp();

-- Status definitions:
--   onboarding — new org, being set up (default)
--   demo       — trial period, limited features or usage caps
--   active     — paying client, full access
--   inactive   — churned or paused, data retained but access disabled

-- ── Users ────────────────────────────────────────────────────────────────────

CREATE TABLE users (
    id              SERIAL PRIMARY KEY,
    organization_id INTEGER REFERENCES organizations(id),  -- null for superadmins
    email           TEXT NOT NULL,
    first_name      TEXT NOT NULL,
    last_name       TEXT NOT NULL,
    full_name       TEXT GENERATED ALWAYS AS (first_name || ' ' || last_name) STORED,
    phone           TEXT,                          -- optional phone number
    role            TEXT NOT NULL DEFAULT 'crew',  -- 'superadmin', 'admin', 'reviewer', 'crew'
    is_active       BOOLEAN NOT NULL DEFAULT TRUE, -- deactivate instead of delete
    deactivated_at  TIMESTAMPTZ,                   -- when the user was deactivated (null if active)
    password_hash   TEXT,                          -- null until auth is implemented
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Roles:
--   superadmin  — platform owner (Brandon). Sees all orgs, can impersonate any user.
--   admin       — org-level admin (Dylan). Manages their org's projects, users, requirements.
--   reviewer    — can review and approve/reject compliance reports.
--   crew        — field crew. Can run checks on assigned projects.

CREATE UNIQUE INDEX idx_users_email_lower ON users(LOWER(email));
CREATE INDEX idx_users_org ON users(organization_id);

CREATE TRIGGER users_update_timestamp BEFORE UPDATE ON users
  FOR EACH ROW EXECUTE FUNCTION update_timestamp();

-- ── Impersonation Log ────────────────────────────────────────────────────────
-- Tracks when a superadmin impersonates another user. Every action taken
-- while impersonating is auditable back to the real user.

CREATE TABLE impersonation_log (
    id                  SERIAL PRIMARY KEY,
    superadmin_id       INTEGER NOT NULL REFERENCES users(id),
    impersonated_user_id INTEGER NOT NULL REFERENCES users(id),
    started_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at            TIMESTAMPTZ,
    reason              TEXT                       -- optional note for audit trail
);

CREATE INDEX idx_impersonation_admin ON impersonation_log(superadmin_id);
CREATE INDEX idx_impersonation_user ON impersonation_log(impersonated_user_id);

-- ── Projects ─────────────────────────────────────────────────────────────────

CREATE TABLE projects (
    id                  SERIAL PRIMARY KEY,
    organization_id     INTEGER NOT NULL REFERENCES organizations(id),
    companycam_id       TEXT NOT NULL,             -- CompanyCam project ID
    name                TEXT NOT NULL,
    address             TEXT,
    city                TEXT,
    state               TEXT,
    cached_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),  -- when we last synced from CompanyCam
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX idx_projects_cc_id ON projects(organization_id, companycam_id);
CREATE INDEX idx_projects_org ON projects(organization_id);

-- ── Checklists ───────────────────────────────────────────────────────────────

CREATE TABLE checklists (
    id                      SERIAL PRIMARY KEY,
    project_id              INTEGER NOT NULL REFERENCES projects(id),
    companycam_checklist_id TEXT NOT NULL,          -- CompanyCam checklist ID
    companycam_template_id  TEXT,                   -- which template it was created from
    name                    TEXT NOT NULL,
    -- Derived job parameters (auto-detected or manual)
    manufacturer            TEXT,                   -- 'SolarEdge', 'Tesla', 'Enphase'
    has_battery             BOOLEAN NOT NULL DEFAULT FALSE,
    is_backup_battery       BOOLEAN NOT NULL DEFAULT FALSE,
    is_incentive_state      BOOLEAN NOT NULL DEFAULT FALSE,
    portal_access_granted   BOOLEAN NOT NULL DEFAULT FALSE,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_checklists_project ON checklists(project_id);

-- ── Requirements ─────────────────────────────────────────────────────────────
-- Versioned requirement definitions. When Palmetto changes requirements,
-- we add new rows with a bumped version rather than editing existing ones.

CREATE TABLE requirements (
    id              SERIAL PRIMARY KEY,
    code            TEXT NOT NULL,                  -- 'PS1', 'R1', 'E2', etc.
    version         INTEGER NOT NULL DEFAULT 1,
    section         TEXT NOT NULL,                  -- 'Project Site', 'Roof', 'Electrical', etc.
    title           TEXT NOT NULL,
    condition_json  TEXT NOT NULL,                  -- JSON: which job types this applies to
    task_titles     TEXT[] NOT NULL DEFAULT '{}',   -- CompanyCam task titles to match
    keywords        TEXT[] NOT NULL DEFAULT '{}',   -- fallback keyword matching
    validation_prompt TEXT NOT NULL,                -- prompt sent to vision model
    is_optional     BOOLEAN NOT NULL DEFAULT FALSE,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,  -- soft delete when requirements are removed
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX idx_requirements_code_version ON requirements(code, version);

-- ── Reports ──────────────────────────────────────────────────────────────────

CREATE TABLE reports (
    id              SERIAL PRIMARY KEY,
    project_id      INTEGER NOT NULL REFERENCES projects(id),
    checklist_id    INTEGER REFERENCES checklists(id),
    run_by          INTEGER REFERENCES users(id),
    -- Job parameters used for this run
    manufacturer    TEXT NOT NULL,
    has_battery     BOOLEAN NOT NULL DEFAULT FALSE,
    is_backup_battery BOOLEAN NOT NULL DEFAULT FALSE,
    is_incentive_state BOOLEAN NOT NULL DEFAULT FALSE,
    portal_access_granted BOOLEAN NOT NULL DEFAULT FALSE,
    -- Summary
    total_required  INTEGER NOT NULL DEFAULT 0,
    total_passed    INTEGER NOT NULL DEFAULT 0,
    total_failed    INTEGER NOT NULL DEFAULT 0,
    total_missing   INTEGER NOT NULL DEFAULT 0,
    status          TEXT NOT NULL DEFAULT 'running',  -- 'running', 'complete', 'error'
    -- Timestamps
    started_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_reports_project ON reports(project_id);
CREATE INDEX idx_reports_run_by ON reports(run_by);
CREATE INDEX idx_reports_status ON reports(status);

-- ── Requirement Results ──────────────────────────────────────────────────────
-- One row per requirement per report run.

CREATE TABLE requirement_results (
    id              SERIAL PRIMARY KEY,
    report_id       INTEGER NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
    requirement_id  INTEGER NOT NULL REFERENCES requirements(id),
    status          TEXT NOT NULL,                  -- 'PASS', 'FAIL', 'MISSING', 'ERROR', 'N/A'
    reason          TEXT,                           -- AI-generated explanation
    photo_urls      JSONB DEFAULT '{}',             -- {1: "https://...", 2: "https://..."}
    candidates      INTEGER DEFAULT 0,             -- how many photos were reviewed
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_results_report ON requirement_results(report_id);
CREATE INDEX idx_results_requirement ON requirement_results(requirement_id);
CREATE INDEX idx_results_status ON requirement_results(status);

-- ── Run Pricing ──────────────────────────────────────────────────────────────
-- Track API costs per report for billing and cost monitoring.

CREATE TABLE run_pricing (
    id              SERIAL PRIMARY KEY,
    report_id       INTEGER NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
    model           TEXT NOT NULL,                  -- 'claude-haiku-4-5-20251001'
    input_tokens    INTEGER NOT NULL DEFAULT 0,
    output_tokens   INTEGER NOT NULL DEFAULT 0,
    api_calls       INTEGER NOT NULL DEFAULT 0,     -- number of vision calls made
    estimated_cost  NUMERIC(10,6) NOT NULL DEFAULT 0, -- USD
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_pricing_report ON run_pricing(report_id);

-- ── Requirement Snapshots ────────────────────────────────────────────────────
-- Stores Palmetto page baselines for change detection.

CREATE TABLE requirement_snapshots (
    id              SERIAL PRIMARY KEY,
    url             TEXT NOT NULL,
    content_hash    TEXT NOT NULL,
    content_text    TEXT NOT NULL,
    checked_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
