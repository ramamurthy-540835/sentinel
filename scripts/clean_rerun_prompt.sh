#!/bin/bash
#
# clean_rerun_prompt.sh
#
# Clean rerun of the full Sentinel audit for a specific prompt.
# This removes previous local reports and BigQuery data for the prompt,
# then runs a fresh audit.
#
# Usage:
#   ./scripts/clean_rerun_prompt.sh <prompt_id> [--write-bq]
#
# Examples:
#   ./scripts/clean_rerun_prompt.sh 1076043101836935168 --write-bq
#   ./scripts/clean_rerun_prompt.sh 3381323161097207808

set -euo pipefail

if [[ $# -lt 1 ]]; then
    echo "Usage: $0 <prompt_id> [--write-bq]"
    echo ""
    echo "Examples:"
    echo "  $0 1076043101836935168 --write-bq"
    echo "  $0 3381323161097207808"
    exit 1
fi

PROMPT_ID="$1"
shift

WRITE_BQ=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --write-bq)
            WRITE_BQ=true
            shift
            ;;
        *)
            echo "Unknown argument: $1"
            exit 1
            ;;
    esac
done

TARGET_PROJECT="../coder"

echo "======================================================================"
echo "PRISM Sentinel - CLEAN RERUN for Prompt: $PROMPT_ID"
echo "======================================================================"

# Step 1: Clean local reports
echo ""
echo "[1/3] Cleaning local reports for $PROMPT_ID..."
rm -rf "reports/$PROMPT_ID"
echo "      Local reports removed."

# Step 2: Clean BigQuery data for this prompt
echo ""
echo "[2/3] Cleaning previous BigQuery data for prompt $PROMPT_ID..."
bq query --use_legacy_sql=false --format=none "
    DELETE FROM \`ctoteam.prism_sentinel_audit.audit_runs\` 
    WHERE prompt_id='${PROMPT_ID}';

    DELETE FROM \`ctoteam.prism_sentinel_audit.audit_findings\` 
    WHERE prompt_id='${PROMPT_ID}';

    DELETE FROM \`ctoteam.prism_sentinel_audit.requirement_traceability\` 
    WHERE prompt_id='${PROMPT_ID}';

    DELETE FROM \`ctoteam.prism_sentinel_audit.audit_artifacts\` 
    WHERE prompt_id='${PROMPT_ID}';
" 2>/dev/null || echo "      (Some deletes may have had no matching rows)"

echo "      BigQuery data cleaned for prompt $PROMPT_ID."

# Step 3: Run fresh audit
echo ""
echo "[3/3] Running fresh audit..."
CMD="./scripts/run_sentinel_all.sh \"$TARGET_PROJECT\" --prompt-id \"$PROMPT_ID\""

if $WRITE_BQ; then
    CMD="$CMD --write-bq"
fi

eval $CMD

echo ""
echo "======================================================================"
echo "Clean rerun completed for prompt $PROMPT_ID"
echo "======================================================================"
