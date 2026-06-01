#!/bin/bash
# PRISM Sentinel - Full Audit Orchestrator
# Supports optional BigQuery + GCS sync via --write-bq

set -euo pipefail

WRITE_BQ=false
TARGET_PROJECT=""
PROMPT_ID=""
CLEAN_RERUN=false

# Parse arguments (target first, then optional flags)
while [[ $# -gt 0 ]]; do
    case $1 in
        --write-bq)
            WRITE_BQ=true
            shift
            ;;
        --prompt-id)
            PROMPT_ID="$2"
            shift 2
            ;;
        --clean)
            CLEAN_RERUN=true
            shift
            ;;
        -*)
            echo "Unknown option: $1" >&2
            exit 1
            ;;
        *)
            if [[ -z "$TARGET_PROJECT" ]]; then
                TARGET_PROJECT="$1"
            else
                echo "Unexpected argument: $1" >&2
                exit 1
            fi
            shift
            ;;
    esac
done

TARGET_PROJECT=${TARGET_PROJECT:-/home/appadmin/projects/Ram_Projects/DiracDelta/gcloud_run}

# === Clean Rerun Support ===
if [[ "$CLEAN_RERUN" == true && -n "$PROMPT_ID" ]]; then
    echo "=== CLEAN RERUN MODE for prompt $PROMPT_ID ==="
    echo "Removing local reports for $PROMPT_ID..."
    rm -rf "reports/$PROMPT_ID"

    echo "Removing previous BigQuery data for prompt $PROMPT_ID..."
    bq query --use_legacy_sql=false --format=none "
        DELETE FROM \`ctoteam.prism_sentinel_audit.audit_runs\` WHERE prompt_id='${PROMPT_ID}';
        DELETE FROM \`ctoteam.prism_sentinel_audit.audit_findings\` WHERE prompt_id='${PROMPT_ID}';
        DELETE FROM \`ctoteam.prism_sentinel_audit.requirement_traceability\` WHERE prompt_id='${PROMPT_ID}';
        DELETE FROM \`ctoteam.prism_sentinel_audit.audit_artifacts\` WHERE prompt_id='${PROMPT_ID}';
    " 2>/dev/null || echo "  (Some BigQuery deletes may have had no rows or failed silently)"

    echo "Clean rerun preparation complete."
    echo ""
fi

# Determine reports directory: per-prompt if PROMPT_ID is provided (clean isolation)
if [[ -n "$PROMPT_ID" ]]; then
    # Use the dedicated helper if available (recommended)
    if [[ -x "./scripts/prepare_prompt_reports_dir.sh" ]]; then
        REPORTS_DIR=$(./scripts/prepare_prompt_reports_dir.sh "$PROMPT_ID")
    else
        REPORTS_DIR="reports/$PROMPT_ID"
        mkdir -p "$REPORTS_DIR"
        export SENTINEL_REPORTS_DIR="$REPORTS_DIR"
    fi
else
    REPORTS_DIR="reports"
    mkdir -p "$REPORTS_DIR"
fi

echo "================================================================================"
echo "PRISM Sentinel Quality Agent - Full Audit Execution"
echo "Target Project: $TARGET_PROJECT"
if [[ -n "$PROMPT_ID" ]]; then
    echo "Original Prompt ID: $PROMPT_ID"
fi
if $WRITE_BQ; then
    echo "BigQuery Sync: ENABLED (ctoteam.prism_sentinel_audit)"
fi
echo "================================================================================"

echo "Using reports directory: $REPORTS_DIR"
export SENTINEL_REPORTS_DIR="$REPORTS_DIR"   # agents can respect this if updated

# Generate audit run ID early if we are writing to BQ (UUID required by schema)
AUDIT_RUN_ID=""
if $WRITE_BQ; then
    if command -v uuidgen >/dev/null 2>&1; then
        AUDIT_RUN_ID=$(uuidgen)
    else
        AUDIT_RUN_ID=$(python3 -c 'import uuid; print(uuid.uuid4())')
    fi
    echo "Audit Run ID: $AUDIT_RUN_ID"
    echo ""
fi

STARTED_AT=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

echo "1. Running Requirement Mapping..."
./scripts/run_requirement_mapping.sh "$TARGET_PROJECT"

echo "2. Running Gap Analysis..."
./scripts/run_gap_analysis.sh "$TARGET_PROJECT"

echo "3. Running Code Quality Review..."
./scripts/run_code_quality.sh "$TARGET_PROJECT"

echo "4. Running Environment Validation..."
./scripts/run_env_validation.sh "$TARGET_PROJECT"

echo "5. Running GCS Audit..."
./scripts/run_gcs_audit.sh "$TARGET_PROJECT"

echo "6. Packaging Audit Evidence..."
./scripts/run_audit_package.sh "$TARGET_PROJECT"

# Optional: Write everything to GCS + BigQuery
if $WRITE_BQ; then
    echo ""
    echo "7. Writing audit results to BigQuery..."
    ./scripts/write_audit_to_bigquery.sh "$TARGET_PROJECT" "$AUDIT_RUN_ID" "$PROMPT_ID" --reports-dir "$REPORTS_DIR"
fi

echo ""
echo "================================================================================"
echo "PRISM Sentinel Audit Complete."
if [[ -n "$PROMPT_ID" ]]; then
    echo "  Prompt ID: $PROMPT_ID"
    echo "  Reports directory: $REPORTS_DIR/"
else
    echo "  Reports directory: reports/"
fi
if $WRITE_BQ; then
    echo "  Run ID: $AUDIT_RUN_ID"
    echo "  GCS: gs://agentproject/sentinel-audits/coder/$AUDIT_RUN_ID/"
    echo "  BigQuery: ctoteam.prism_sentinel_audit.* (linked by audit_run_id)"
    echo "  Query example: bq query --use_legacy_sql=false \"SELECT * FROM \\\`ctoteam.prism_sentinel_audit.audit_runs\\\` WHERE audit_run_id='${AUDIT_RUN_ID}'\""
else
    echo "  (Run with --write-bq to also upload to GCS and insert into BigQuery)"
echo ""
echo "Clean rerun options:"
echo "  --clean                Delete previous local reports + BigQuery data for the prompt before running"
echo ""
echo "Recommended for clean reruns:"
echo "  ./scripts/clean_rerun_prompt.sh <prompt_id> [--write-bq]"
echo "  (This is the preferred way — it does full cleanup + fresh run automatically)"
fi
echo "================================================================================"

