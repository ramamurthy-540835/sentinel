-- Step 3: Multimodal extraction using BigQuery ML.GENERATE_TEXT
-- Uses flatten_json_output=TRUE so parsed text is in ml_generate_text_llm_result
CREATE OR REPLACE TABLE `ctoteam.prism_prompt_catalog.extracted_attachment_text` AS
SELECT
  REGEXP_EXTRACT(uri, r'saved-prompts/([^/]+)/') AS prompt_id,
  REGEXP_EXTRACT(uri, r'/silver/([^/]+)/') AS run_id,
  REGEXP_EXTRACT(uri, r'attachments/([^/]+)\\.json$') AS attachment_id,
  uri AS gcs_uri,
  content_type,
  size,
  ml_generate_text_llm_result AS transcribed_content,
  ml_generate_text_status AS extraction_status,
  CURRENT_TIMESTAMP() AS created_at
FROM ML.GENERATE_TEXT(
  MODEL `ctoteam.prism_prompt_catalog.gemini_flash_model`,
  TABLE `ctoteam.prism_prompt_catalog.prompt_attachments_object_table`,
  STRUCT(
    'Identify layout and transcribe all textual/tabular/structural content into clean Markdown.' AS prompt,
    0.1 AS temperature,
    2048 AS max_output_tokens,
    TRUE AS flatten_json_output
  )
);
