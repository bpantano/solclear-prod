-- Migration 003: Per-call Anthropic API cost logging
--
-- One row per Anthropic API call we make. Lets us attribute cost to a
-- specific report / requirement, slice by model, and aggregate for
-- per-org billing later.
--
-- run_pricing (already defined in schema.sql) remains as a per-report
-- rollup — this table is the source-of-truth for individual calls.
--
-- Run on Railway:
--   conda run python tools/run_migration.py migrations/003_api_call_log.sql
-- Or paste the SQL into Railway dashboard → Data → Query.
-- Safe to re-run: uses IF NOT EXISTS.

CREATE TABLE IF NOT EXISTS api_call_log (
    id                  SERIAL PRIMARY KEY,
    report_id           INTEGER REFERENCES reports(id) ON DELETE CASCADE,
    requirement_code    TEXT,
    purpose             TEXT,
    model               TEXT NOT NULL,
    input_tokens        INTEGER NOT NULL DEFAULT 0,
    output_tokens       INTEGER NOT NULL DEFAULT 0,
    cost_usd            NUMERIC(12, 6) NOT NULL DEFAULT 0,
    duration_ms         INTEGER,
    called_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_api_call_log_report ON api_call_log(report_id);
CREATE INDEX IF NOT EXISTS idx_api_call_log_model  ON api_call_log(model);
CREATE INDEX IF NOT EXISTS idx_api_call_log_called ON api_call_log(called_at);
