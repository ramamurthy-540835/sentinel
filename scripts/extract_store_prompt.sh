#!/bin/bash
# Extract and Store Prompt in GCS + BigQuery Catalog (Phase 2 Medallion Edition)
# Usage: ./scripts/extract_store_prompt.sh <prompt_id> [--force]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

PROMPT_ID="${1:?ERROR: prompt_id required}"
FORCE="${2:-}"

echo "=============================================================="
echo "PRISM PROMPT LAKEHOUSE: EXTRACT & STORE"
echo "=============================================================="
echo "Prompt ID:  $PROMPT_ID"
echo "Project:    ctoteam"
echo "GCS Bucket: gs://agentproject/"
echo "Force Flag: ${FORCE:-none}"
echo ""

# STAGE 1: Extract & Upload to GCS Medallion Layers
echo "[STAGE 1] Running Medallion Extraction Agent..."

# Capture ONLY stdout (which is standard JSON metadata) into METADATA_JSON.
# Real-time stderr logs from python go straight to the console.
METADATA_JSON=$(python3 agents/gcs_prompt_store.py \
  --prompt-id "$PROMPT_ID" \
  --project-id "ctoteam" \
  --location "us-central1" \
  --bucket "agentproject" \
  $([[ -n "$FORCE" ]] && echo "--force"))

# Extract version control variables
RUN_ID=$(echo "$METADATA_JSON" | python3 -c "import sys, json; print(json.load(sys.stdin).get('run_id', ''))")
REPEAT_MODE=$(echo "$METADATA_JSON" | python3 -c "import sys, json; print(json.load(sys.stdin).get('repeat_mode', ''))")
VERSION_NUMBER=$(echo "$METADATA_JSON" | python3 -c "import sys, json; print(json.load(sys.stdin).get('version_number', ''))")
PARENT_RUN_ID=$(echo "$METADATA_JSON" | python3 -c "import sys, json; print(json.load(sys.stdin).get('parent_run_id', ''))")

if [[ -z "$RUN_ID" || "$RUN_ID" == "null" ]]; then
  echo "ERROR: Failed to extract run_id from extraction metadata."
  exit 1
fi

# Handle Unchanged/Skip Flow
if [[ "$REPEAT_MODE" == "unchanged_skip" ]]; then
  echo ""
  echo "--------------------------------------------------------------"
  echo "✓ Change Detection: No changes detected for prompt_uid."
  echo "✓ Extraction skipped (repeat_mode: unchanged_skip)."
  echo "✓ Version remains active at: Version $VERSION_NUMBER"
  echo "--------------------------------------------------------------"
  
  echo ""
  echo "[STAGE 2] Registering Skip Event in Catalog..."
  
  TEMP_META_FILE=$(mktemp)
  echo "$METADATA_JSON" > "$TEMP_META_FILE"
  
  python3 agents/bigquery_prompt_catalog.py \
    --prompt-id "$PROMPT_ID" \
    --run-id "$RUN_ID" \
    --project-id "ctoteam" \
    --metadata-file "$TEMP_META_FILE"
    
  rm -f "$TEMP_META_FILE"
  
  echo "=============================================================="
  echo "EXTRACTION PROCESS SKIPPED (UNCHANGED)"
  echo "=============================================================="
  exit 0
fi

echo "✓ Uploaded Medallion Layers (run_id: ${RUN_ID:0:8}...)"

# STAGE 2: Register in BigQuery SCD Type 2 Catalog
echo ""
echo "[STAGE 2] Registering in BigQuery SCD Type 2 Catalog..."

RUN_FOLDER="$PROJECT_ROOT/saved_prompts/$PROMPT_ID/runs/$RUN_ID"

TEMP_META_FILE=$(mktemp)
echo "$METADATA_JSON" > "$TEMP_META_FILE"

python3 agents/bigquery_prompt_catalog.py \
  --prompt-id "$PROMPT_ID" \
  --run-id "$RUN_ID" \
  --project-id "ctoteam" \
  --metadata-file "$TEMP_META_FILE" \
  --run-folder "$RUN_FOLDER"

rm -f "$TEMP_META_FILE"

echo ""
echo "=============================================================="
echo "EXTRACTION COMPLETE"
echo "=============================================================="
echo ""
echo "GCS Medallion Locations:"
echo "  Bronze: gs://agentproject/bronze/vertexai:$PROMPT_ID/$RUN_ID/"
echo "  Silver: gs://agentproject/silver/vertexai:$PROMPT_ID/$RUN_ID/"
echo "  Gold:   gs://agentproject/gold/vertexai:$PROMPT_ID/$RUN_ID/"
echo ""
echo "Version Lineage:"
if [[ -n "$PARENT_RUN_ID" ]]; then
  echo "  Version $VERSION_NUMBER (Current: $RUN_ID) -> Version $((VERSION_NUMBER-1)) (Parent: $PARENT_RUN_ID)"
else
  echo "  Version $VERSION_NUMBER (Current: $RUN_ID) [Initial Version]"
fi
echo ""
echo "Query Latest Extractions:"
echo "  bq query --use_legacy_sql=false '"
echo "    SELECT prompt_id, run_id, chunk_count, user_message_count"
echo "    FROM ctoteam.prism_prompt_catalog.latest_runs"
echo "    WHERE prompt_id = \"vertexai:$PROMPT_ID\""
echo "    ORDER BY created_at DESC;'"
echo "  '"
echo ""
echo "View Run Metadata Pointer:"
echo "  gsutil cat gs://agentproject/gold/vertexai:$PROMPT_ID/latest.json"
echo ""
