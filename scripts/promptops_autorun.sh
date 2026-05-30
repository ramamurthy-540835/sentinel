#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  ./scripts/promptops_autorun.sh --prompt-id <id> [--mode dry-run|live] [--project ctoteam] [--bucket agentproject]
USAGE
}

PROMPT_ID=""
MODE="dry-run"
PROJECT_ID="ctoteam"
BUCKET="agentproject"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --prompt-id) PROMPT_ID="${2:-}"; shift 2 ;;
    --mode) MODE="${2:-}"; shift 2 ;;
    --project) PROJECT_ID="${2:-}"; shift 2 ;;
    --bucket) BUCKET="${2:-}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown arg: $1"; usage; exit 2 ;;
  esac
done

[[ -n "$PROMPT_ID" ]] || { echo "ERROR: --prompt-id is required"; exit 2; }
[[ "$MODE" == "dry-run" || "$MODE" == "live" ]] || { echo "ERROR: --mode must be dry-run or live"; exit 2; }

PROMPT_UID="vertexai:${PROMPT_ID}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
LOCAL_RUN_TAG="${TIMESTAMP}_$(openssl rand -hex 4 2>/dev/null || echo localrun)"
RUN_BASE="$ROOT_DIR/runs/$PROMPT_UID/$LOCAL_RUN_TAG"
mkdir -p "$RUN_BASE/artifacts" "$RUN_BASE/logs" "$RUN_BASE/stages"

stage_start() { STAGE_NAME="$1"; STAGE_TS_START="$(date -u +%Y-%m-%dT%H:%M:%SZ)"; echo "[STAGE] $STAGE_NAME start"; }
stage_end() {
  local stage_name="$1" status="$2" note="${3:-}" stage_ts_end
  stage_ts_end="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  cat > "$RUN_BASE/stages/${stage_name}.json" <<JSON
{"prompt_id":"${PROMPT_ID}","prompt_uid":"${PROMPT_UID}","local_run_tag":"${LOCAL_RUN_TAG}","mode":"${MODE}","project_id":"${PROJECT_ID}","stage":"${stage_name}","status":"${status}","started_at":"${STAGE_TS_START}","ended_at":"${stage_ts_end}","note":"${note}"}
JSON
  echo "[STAGE] $stage_name $status"
}

manifest_write() {
  local extracted_chars=0
  [[ -f "$RUN_BASE/artifacts/prompt_full.txt" ]] && extracted_chars="$(wc -m < "$RUN_BASE/artifacts/prompt_full.txt" | tr -d ' ')"
  cat > "$RUN_BASE/manifest.json" <<JSON
{"prompt_id":"${PROMPT_ID}","prompt_uid":"${PROMPT_UID}","local_run_tag":"${LOCAL_RUN_TAG}","mode":"${MODE}","project_id":"${PROJECT_ID}","bucket":"${BUCKET}","run_base":"${RUN_BASE}","extracted_chars":${extracted_chars},"created_at":"$(date -u +%Y-%m-%dT%H:%M:%SZ)"}
JSON
}

cd "$ROOT_DIR"
stage_start "ingest_extract_store"
if ./scripts/extract_store_prompt.sh "$PROMPT_ID" > "$RUN_BASE/logs/extract_store.log" 2>&1; then
  stage_end "ingest_extract_store" "completed" "extract_store_prompt.sh succeeded"
else
  stage_end "ingest_extract_store" "failed" "see logs/extract_store.log"; manifest_write; exit 1
fi

stage_start "resolve_latest_prompt_text"
if [[ -f "$ROOT_DIR/saved_prompts/$PROMPT_ID/extracted_content.txt" ]]; then
  cp "$ROOT_DIR/saved_prompts/$PROMPT_ID/extracted_content.txt" "$RUN_BASE/artifacts/prompt_full.txt"
  stage_end "resolve_latest_prompt_text" "completed" "copied extracted_content.txt"
elif [[ -f "$ROOT_DIR/saved_prompts/$PROMPT_ID/master.md" ]]; then
  cp "$ROOT_DIR/saved_prompts/$PROMPT_ID/master.md" "$RUN_BASE/artifacts/prompt_full.txt"
  stage_end "resolve_latest_prompt_text" "completed" "copied master.md"
else
  stage_end "resolve_latest_prompt_text" "failed" "no prompt text found"; manifest_write; exit 1
fi

stage_start "extract_attachments_text"
cat > "$RUN_BASE/artifacts/attachments_query.sql" <<SQL
SELECT
  a.prompt_uid,
  a.attachment_id,
  a.attachment_type,
  COALESCE(e.transcribed_content, "[Attachment has no text or is unparsed binary]") AS transcribed_text,
  e.raw_response,
  a.created_at
FROM
  \`${PROJECT_ID}.prism_prompt_catalog.prompt_attachments\` a
LEFT JOIN
  \`${PROJECT_ID}.prism_prompt_catalog.extracted_attachment_text\` e
  ON a.attachment_id = e.attachment_id
WHERE a.prompt_uid = "${PROMPT_UID}"
ORDER BY a.created_at;
SQL
if bq query --use_legacy_sql=false --format=json < "$RUN_BASE/artifacts/attachments_query.sql" > "$RUN_BASE/artifacts/attachments_text.json" 2> "$RUN_BASE/logs/attachments_query.log"; then
  stage_end "extract_attachments_text" "completed" "attachments extracted"
else
  stage_end "extract_attachments_text" "failed" "see logs/attachments_query.log"; manifest_write; exit 1
fi

stage_start "budget_estimate"
PROMPT_CHARS="$(wc -m < "$RUN_BASE/artifacts/prompt_full.txt" | tr -d ' ')"
APPROX_TOKENS=$((PROMPT_CHARS / 4))
EST_OUTPUT_TOKENS=$((APPROX_TOKENS / 5))
EST_INPUT_RATE=0.00000125
EST_OUTPUT_RATE=0.000005
EST_BUDGET=$(python3 - <<PY
inp=${APPROX_TOKENS}; out=${EST_OUTPUT_TOKENS}; ir=${EST_INPUT_RATE}; orate=${EST_OUTPUT_RATE}
print(round(inp*ir + out*orate, 6))
PY
)
cat > "$RUN_BASE/artifacts/budget_estimate.json" <<JSON
{"prompt_chars":${PROMPT_CHARS},"estimated_input_tokens":${APPROX_TOKENS},"estimated_output_tokens":${EST_OUTPUT_TOKENS},"estimated_total_usd":${EST_BUDGET}}
JSON
stage_end "budget_estimate" "completed" "estimated_total_usd=${EST_BUDGET}"

stage_start "publish_gcs"
if [[ "$MODE" == "live" ]]; then
  GCS_PREFIX="gs://${BUCKET}/prompt-pipeline/${PROMPT_UID}/${LOCAL_RUN_TAG}/"
  if gsutil -m cp -r "$RUN_BASE/artifacts" "$GCS_PREFIX" > "$RUN_BASE/logs/publish_gcs.log" 2>&1; then
    echo "$GCS_PREFIX" > "$RUN_BASE/artifacts/published_gcs_prefix.txt"
    stage_end "publish_gcs" "completed" "published to ${GCS_PREFIX}"
  else
    stage_end "publish_gcs" "failed" "see logs/publish_gcs.log"; manifest_write; exit 1
  fi
else
  stage_end "publish_gcs" "skipped" "dry-run mode"
fi

manifest_write
echo "Run complete: $RUN_BASE"
