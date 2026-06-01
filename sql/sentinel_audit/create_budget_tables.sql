-- Budget and Consumption Tracking for Sentinel (per prompt / project)
-- Run with: bq query --use_legacy_sql=false -f sql/sentinel_audit/create_budget_tables.sql

-- 1. Budget allocation per prompt (or project)
CREATE TABLE IF NOT EXISTS `ctoteam.prism_sentinel_audit.prompt_budgets` (
  prompt_id STRING NOT NULL,
  monthly_budget_usd FLOAT64 NOT NULL,
  allocated_by STRING,
  notes STRING,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
)
CLUSTER BY prompt_id;

-- 2. Consumption log (every estimation / audit run contributes here)
-- We can also aggregate from audit_runs, but having a dedicated table makes querying easier.
CREATE TABLE IF NOT EXISTS `ctoteam.prism_sentinel_audit.prompt_consumption` (
  consumption_id STRING NOT NULL,
  prompt_id STRING NOT NULL,
  audit_run_id STRING,
  tokens_in INT64,
  tokens_out INT64,
  estimated_cost_usd FLOAT64,
  functional_points FLOAT64,
  complexity_band STRING,
  run_type STRING,                    -- estimation | full_audit | incremental
  source STRING,                      -- local | gcs | bq
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
)
CLUSTER BY prompt_id, created_at;

-- Optional: View for current remaining budget per prompt
-- CREATE OR REPLACE VIEW `ctoteam.prism_sentinel_audit.vw_prompt_budget_status` AS ...
