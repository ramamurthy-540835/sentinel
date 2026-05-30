-- Step 2: Object table over nested Silver attachment assets
CREATE OR REPLACE EXTERNAL TABLE `ctoteam.prism_prompt_catalog.prompt_attachments_object_table`
WITH CONNECTION `ctoteam.us.vertex_conn`
OPTIONS(
  object_metadata = "SIMPLE",
  uris = ["gs://agentproject/saved-prompts/*/silver/*/attachments/*"]
);
