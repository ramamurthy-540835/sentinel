-- PRISM Sentinel Audit Catalog
-- Dataset: ctoteam.prism_sentinel_audit
-- Run with: bq query --use_legacy_sql=false -f sql/sentinel_audit/create_tables.sql

-- Create dataset if not exists (run separately or via init script)
-- bq mk --dataset --location=us-central1 ctoteam:prism_sentinel_audit

CREATE TABLE IF NOT EXISTS `ctoteam.prism_sentinel_audit.audit_runs` (
  audit_run_id STRING NOT NULL,
  target_project_path STRING,
  target_project_name STRING,
  overall_score FLOAT64,
  overall_status STRING,           -- PASSED | WARNINGS | CRITICAL_ISSUES | FAILED | BQ_SYNC_FAILED
  started_at TIMESTAMP,
  completed_at TIMESTAMP,
  report_gcs_uri STRING,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
)
CLUSTER BY target_project_name, audit_run_id;

CREATE TABLE IF NOT EXISTS `ctoteam.prism_sentinel_audit.audit_findings` (
  finding_id STRING NOT NULL,
  audit_run_id STRING NOT NULL,
  severity STRING,                 -- critical | major | minor | info
  category STRING,
  file_path STRING,
  line_number INT64,
  finding_text STRING,
  recommendation STRING,
  owner_hint STRING,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
)
CLUSTER BY audit_run_id, severity;

CREATE TABLE IF NOT EXISTS `ctoteam.prism_sentinel_audit.requirement_traceability` (
  trace_id STRING NOT NULL,
  audit_run_id STRING NOT NULL,
  requirement_id STRING,
  requirement_text STRING,
  implementation_file STRING,
  test_file STRING,
  status STRING,                   -- Implemented | Missing | Partial
  gap_text STRING,
  risk_level STRING,               -- high | medium | low
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
)
CLUSTER BY audit_run_id, status;

CREATE TABLE IF NOT EXISTS `ctoteam.prism_sentinel_audit.audit_artifacts` (
  artifact_id STRING NOT NULL,
  audit_run_id STRING NOT NULL,
  artifact_type STRING,            -- report_md | report_json | evidence_package | other
  local_path STRING,
  gcs_uri STRING,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
)
CLUSTER BY audit_run_id, artifact_type;

-- Optional: Add some useful views later
-- Example: Latest runs per project
