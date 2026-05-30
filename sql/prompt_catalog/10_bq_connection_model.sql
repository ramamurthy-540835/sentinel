-- Step 1: Connection + Remote Model (BigQuery Way)
CREATE CONNECTION IF NOT EXISTS `ctoteam.us.vertex_conn`
OPTIONS(
  connection_type = 'CLOUD_RESOURCE'
);

CREATE OR REPLACE MODEL `ctoteam.prism_prompt_catalog.gemini_flash_model`
REMOTE WITH CONNECTION `ctoteam.us.vertex_conn`
OPTIONS(
  endpoint = 'gemini-1.5-flash-002'
);
