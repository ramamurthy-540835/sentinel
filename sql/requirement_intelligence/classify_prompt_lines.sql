-- classify_prompt_lines.sql
-- Deterministic noise classification for raw prompt lines
-- Run this after loading data into raw_prompt_lines for a specific prompt_id

DECLARE target_prompt_id STRING DEFAULT '3381323161097207808';

-- Step 1: Classify obvious noise using deterministic rules
UPDATE `ctoteam.prism_requirement_intelligence.requirement_candidates`
SET 
  is_requirement_candidate = FALSE,
  noise_type = CASE
    WHEN REGEXP_CONTAINS(LOWER(line_text), r'error:|traceback|exception|typeerror|valueerror') THEN 'ERROR_TRACE'
    WHEN REGEXP_CONTAINS(LOWER(line_text), r'^\s*(gsutil|bq |curl |python |bash |sh |use_legacy_sql)') THEN 'SHELL_COMMAND'
    WHEN REGEXP_CONTAINS(LOWER(line_text), r'select |insert |update |delete |create table|from `') THEN 'SQL_SNIPPET'
    WHEN REGEXP_CONTAINS(line_text, r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}') THEN 'UUID_OR_RUN_ID'
    WHEN REGEXP_CONTAINS(line_text, r'^[\-\=\_\*\#\s]{10,}$') THEN 'MARKDOWN_SEPARATOR'
    WHEN REGEXP_CONTAINS(LOWER(line_text), r'success:|info:|debug:|warning:') THEN 'LOG'
    WHEN REGEXP_CONTAINS(LOWER(line_text), r'gemini-1\.5|gemini-2\.0|gemini-2\.5') THEN 'MODEL_CHAT'
    ELSE 'DUPLICATE'  -- Will be refined later
  END
WHERE prompt_id = target_prompt_id
  AND (is_requirement_candidate IS NULL OR is_requirement_candidate = TRUE)
  AND (
    REGEXP_CONTAINS(LOWER(line_text), r'error:|traceback|exception|typeerror|valueerror')
    OR REGEXP_CONTAINS(LOWER(line_text), r'^\s*(gsutil|bq |curl |python |bash |sh |use_legacy_sql)')
    OR REGEXP_CONTAINS(LOWER(line_text), r'select |insert |update |delete |create table|from `')
    OR REGEXP_CONTAINS(line_text, r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}')
    OR REGEXP_CONTAINS(line_text, r'^[\-\=\_\*\#\s]{10,}$')
    OR REGEXP_CONTAINS(LOWER(line_text), r'success:|info:|debug:|warning:')
    OR REGEXP_CONTAINS(LOWER(line_text), r'gemini-1\.5|gemini-2\.0|gemini-2\.5')
  );

-- Step 2: Mark remaining unclassified rows as potential TRUE_REQUIREMENT candidates
UPDATE `ctoteam.prism_requirement_intelligence.requirement_candidates`
SET 
  is_requirement_candidate = TRUE,
  noise_type = 'TRUE_REQUIREMENT',
  requirement_category = 'UNCATEGORIZED',
  confidence_score = 0.6
WHERE prompt_id = target_prompt_id
  AND is_requirement_candidate IS NULL;

-- Step 3: Basic category assignment for true candidates (can be enhanced with BQML later)
UPDATE `ctoteam.prism_requirement_intelligence.requirement_candidates`
SET requirement_category = 
  CASE 
    WHEN REGEXP_CONTAINS(LOWER(line_text), r'auth|token|secret|credential|security') THEN 'Security'
    WHEN REGEXP_CONTAINS(LOWER(line_text), r'gcs|bigquery|vertex|cloud run|cloud build') THEN 'Infrastructure'
    WHEN REGEXP_CONTAINS(LOWER(line_text), r'test|validation|coverage') THEN 'Testing'
    WHEN REGEXP_CONTAINS(LOWER(line_text), r'extract|parse|chunk|metadata') THEN 'Data'
    WHEN REGEXP_CONTAINS(LOWER(line_text), r'aider|launch|orchestrat|workflow') THEN 'Orchestration'
    ELSE 'Functional'
  END,
  confidence_score = 0.75
WHERE prompt_id = target_prompt_id
  AND noise_type = 'TRUE_REQUIREMENT'
  AND requirement_category = 'UNCATEGORIZED';