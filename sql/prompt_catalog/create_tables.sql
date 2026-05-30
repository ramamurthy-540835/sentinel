-- BigQuery Schema for PRISM Prompt Lakehouse (Phase 2)
-- Dataset: ctoteam.prism_prompt_catalog
-- Stores metadata, version lineages, chunks, attachments, and audit events.

CREATE SCHEMA IF NOT EXISTS `ctoteam.prism_prompt_catalog`
OPTIONS(
  description="PRISM prompt extraction Lakehouse with GCS Medallion artifact registry",
  location="US"
);

-- Table 1: Prompt Versions (SCD Type 2)
CREATE OR REPLACE TABLE `ctoteam.prism_prompt_catalog.prompt_versions` (
  prompt_uid STRING NOT NULL,         -- enterprise primary key (e.g. 'vertexai:3381323161097207808')
  source_prompt_id STRING NOT NULL,   -- source traceability
  source_system STRING NOT NULL,      -- source platform (e.g. 'vertexai', 'openai')
  run_id STRING NOT NULL,             -- UUID v4 run identifier
  parent_run_id STRING,               -- self-referential lineage pointer
  version_number INT64 NOT NULL,      -- auto-incremented per prompt_uid
  is_current BOOL NOT NULL,           -- TRUE if latest active version
  valid_from TIMESTAMP NOT NULL,      -- validity start timestamp
  valid_to TIMESTAMP,                 -- validity end timestamp (NULL if current)
  raw_hash STRING NOT NULL,           -- MD5 hash of raw payload
  extracted_hash STRING NOT NULL,     -- MD5 hash of clean text
  status STRING NOT NULL,             -- success | failed | processing
  repeat_mode STRING NOT NULL,        -- first_run | changed_new_version | force_new_version | unchanged_skip
  bronze_gcs_uri STRING NOT NULL,     -- gs://agentproject/bronze/<prompt_uid>/<run_id>/
  silver_gcs_uri STRING NOT NULL,     -- gs://agentproject/silver/<prompt_uid>/<run_id>/
  gold_gcs_uri STRING NOT NULL,       -- gs://agentproject/gold/<prompt_uid>/<run_id>/
  chunk_count INT64 NOT NULL,
  system_present BOOL NOT NULL,
  user_message_count INT64 NOT NULL,
  model_message_count INT64 NOT NULL,
  text_attachment_count INT64 NOT NULL,
  binary_attachment_count INT64 NOT NULL,
  raw_size_bytes INT64 NOT NULL,
  extracted_chars INT64 NOT NULL
)
PARTITION BY DATE(valid_from)
CLUSTER BY prompt_uid, is_current, status;

-- Table 2: Prompt Chunks (sequential text blocks)
CREATE OR REPLACE TABLE `ctoteam.prism_prompt_catalog.prompt_chunks` (
  prompt_uid STRING NOT NULL,
  run_id STRING NOT NULL,
  version_number INT64 NOT NULL,      -- link back to versions table
  chunk_id STRING NOT NULL,           -- UUID v4
  chunk_order INT64 NOT NULL,         -- 0-indexed sequential order
  chunk_file STRING NOT NULL,         -- e.g. chunk_001.md
  gcs_uri STRING NOT NULL,            -- GCS silver path
  char_count INT64 NOT NULL,
  estimated_tokens INT64 NOT NULL,    -- ~4 chars = 1 token
  role STRING NOT NULL,               -- system | user | model
  artifact_type STRING NOT NULL,      -- text | code | markdown
  created_at TIMESTAMP NOT NULL
)
PARTITION BY DATE(created_at)
CLUSTER BY prompt_uid, run_id, chunk_order;

-- Table 3: Prompt Attachments (multimodal payloads)
CREATE OR REPLACE TABLE `ctoteam.prism_prompt_catalog.prompt_attachments` (
  prompt_uid STRING NOT NULL,
  run_id STRING NOT NULL,
  version_number INT64 NOT NULL,      -- link back to versions table
  attachment_id STRING NOT NULL,      -- UUID v4
  mime_type STRING NOT NULL,          -- mime type of asset
  attachment_type STRING NOT NULL,    -- image | pdf | text | binary
  local_path STRING,                  -- reference local filepath
  gcs_uri STRING NOT NULL,            -- GCS silver path
  size_bytes INT64 NOT NULL,
  decoded BOOL NOT NULL,              -- TRUE if plain-text was decoded
  created_at TIMESTAMP NOT NULL
)
PARTITION BY DATE(created_at)
CLUSTER BY prompt_uid, run_id, attachment_type;

-- Table 4: Prompt Events (Comprehensive Audit Trail)
CREATE OR REPLACE TABLE `ctoteam.prism_prompt_catalog.prompt_events` (
  event_id STRING NOT NULL,           -- UUID v4
  prompt_uid STRING NOT NULL,
  version_number INT64 NOT NULL,      -- version number context
  run_id STRING NOT NULL,             -- extraction run context
  event_type STRING NOT NULL,         -- created | extracting | bronze_completed | etc.
  lifecycle_status STRING NOT NULL,   -- state matching the transitions
  repeat_mode STRING NOT NULL,        -- first_run | changed_new_version | force_new_version | unchanged_skip
  severity STRING NOT NULL,           -- info | warning | error
  message STRING NOT NULL,
  created_at TIMESTAMP NOT NULL
)
PARTITION BY DATE(created_at)
CLUSTER BY prompt_uid, run_id, event_type;

-- View: Latest Run per Prompt (maintains compatibility with Phase 1 queries)
CREATE OR REPLACE VIEW `ctoteam.prism_prompt_catalog.latest_runs` AS
SELECT
  prompt_uid as prompt_id,
  run_id,
  raw_hash,
  extracted_hash,
  status,
  valid_from as created_at,
  silver_gcs_uri as gcs_run_uri,
  chunk_count,
  user_message_count,
  model_message_count,
  text_attachment_count,
  binary_attachment_count
FROM
  `ctoteam.prism_prompt_catalog.prompt_versions`
WHERE
  is_current = TRUE
ORDER BY
  prompt_uid, valid_from DESC;

-- View: Extraction Status Summary
CREATE OR REPLACE VIEW `ctoteam.prism_prompt_catalog.extraction_status` AS
SELECT
  prompt_uid as prompt_id,
  COUNT(DISTINCT run_id) as total_runs,
  COUNT(DISTINCT CASE WHEN status = 'success' THEN run_id END) as successful_runs,
  COUNT(DISTINCT CASE WHEN status = 'failed' THEN run_id END) as failed_runs,
  MAX(valid_from) as last_extraction,
  ARRAY_AGG(DISTINCT raw_hash IGNORE NULLS) as raw_hashes,
  ARRAY_AGG(DISTINCT extracted_hash IGNORE NULLS) as extracted_hashes
FROM
  `ctoteam.prism_prompt_catalog.prompt_versions`
GROUP BY
  prompt_uid;

-- View: Chunk Distribution
CREATE OR REPLACE VIEW `ctoteam.prism_prompt_catalog.chunk_distribution` AS
SELECT
  prompt_uid as prompt_id,
  run_id,
  COUNT(*) as chunk_count,
  SUM(char_count) as total_chars,
  SUM(estimated_tokens) as total_tokens,
  ROUND(AVG(char_count), 0) as avg_chunk_chars,
  MIN(char_count) as min_chunk_chars,
  MAX(char_count) as max_chunk_chars,
  ARRAY_AGG(DISTINCT role) as roles,
  ARRAY_AGG(DISTINCT artifact_type) as artifact_types
FROM
  `ctoteam.prism_prompt_catalog.prompt_chunks`
GROUP BY
  prompt_uid, run_id;
