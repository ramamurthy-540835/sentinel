#!/bin/bash
# PRISM Sentinel - Write local audit results to GCS + BigQuery
# Called by run_sentinel_all.sh when --write-bq is used.

set -euo pipefail

TARGET_PROJECT=${1:?ERROR: target_project_path required}
AUDIT_RUN_ID=${2:?ERROR: audit_run_id (UUID) required}
PROMPT_ID=${3:-""}

TARGET_NAME=$(basename "$TARGET_PROJECT")
GCS_BUCKET="agentproject"
GCS_BASE="gs://${GCS_BUCKET}/sentinel-audits/${TARGET_NAME}/${AUDIT_RUN_ID}/"

echo "================================================================================"
echo "PRISM Sentinel - Write Audit to BigQuery"
echo "Target: $TARGET_PROJECT"
echo "Run ID: $AUDIT_RUN_ID"
if [[ -n "$PROMPT_ID" ]]; then
    echo "Prompt ID: $PROMPT_ID"
fi
echo "GCS:    $GCS_BASE"
echo "================================================================================"

REPORTS_DIR="reports"
mkdir -p "$REPORTS_DIR"

# 1. Upload reports to GCS (using gsutil for reliability)
echo "→ Uploading reports to GCS..."
if gsutil -m cp -r "${REPORTS_DIR}"/* "$GCS_BASE"; then
    echo "✓ Reports uploaded to $GCS_BASE"
else
    echo "⚠️  GCS upload had issues (continuing - local audit is complete)"
fi

# 2. Call the Python writer (handles BigQuery inserts + status logic)
echo ""
echo "→ Writing metadata to BigQuery (ctoteam.prism_sentinel_audit)..."
PYTHON_ARGS=(
    --target-project "$TARGET_PROJECT"
    --audit-run-id "$AUDIT_RUN_ID"
    --gcs-base-uri "$GCS_BASE"
    --reports-dir "$REPORTS_DIR"
)
if [[ -n "$PROMPT_ID" ]]; then
    PYTHON_ARGS+=(--prompt-id "$PROMPT_ID")
fi

python3 agents/bigquery_audit_writer.py "${PYTHON_ARGS[@]}"

echo ""
echo "================================================================================"
echo "PRISM Sentinel BigQuery sync step complete."
echo "  Local reports: $REPORTS_DIR/"
echo "  GCS:           $GCS_BASE"
echo "  BigQuery:      ctoteam.prism_sentinel_audit.* (linked by audit_run_id)"
if [[ -n "$PROMPT_ID" ]]; then
    echo "  Linked Prompt ID: $PROMPT_ID"
fi
echo "================================================================================"
