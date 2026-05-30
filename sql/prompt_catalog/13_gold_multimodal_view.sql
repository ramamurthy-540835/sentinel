-- Step 4: Gold analytical view joining attachment metadata + extracted text
CREATE OR REPLACE VIEW `ctoteam.prism_prompt_catalog.gold_multimodal_attachments` AS
SELECT
  a.prompt_uid,
  a.version_number,
  a.run_id,
  a.attachment_id,
  a.mime_type,
  a.size_bytes,
  COALESCE(e.transcribed_content, '[Attachment has no text or is unparsed binary]') AS transcribed_text,
  e.extraction_status,
  a.created_at
FROM `ctoteam.prism_prompt_catalog.prompt_attachments` a
LEFT JOIN `ctoteam.prism_prompt_catalog.extracted_attachment_text` e
  ON a.attachment_id = e.attachment_id
  AND a.run_id = e.run_id;
