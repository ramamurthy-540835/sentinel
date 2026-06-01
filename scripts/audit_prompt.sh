#!/bin/bash
# Master convenience script for running a full Sentinel audit for one prompt.
#
# Usage:
#   ./scripts/audit_prompt.sh <target_project> --prompt-id <prompt_id> [--write-bq]
#
# Examples:
#   ./scripts/audit_prompt.sh ../coder --prompt-id 1076043101836935168 --write-bq
#   ./scripts/audit_prompt.sh /path/to/my/project --prompt-id 1234567890

set -euo pipefail

if [[ $# -lt 1 ]]; then
    echo "Usage: $0 <target_project> --prompt-id <prompt_id> [--write-bq]"
    exit 1
fi

TARGET_PROJECT="$1"
shift

PROMPT_ID=""
WRITE_BQ=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --prompt-id)
            PROMPT_ID="$2"
            shift 2
            ;;
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

if [[ -z "$PROMPT_ID" ]]; then
    echo "Error: --prompt-id is required"
    exit 1
fi

# Set up clean per-prompt reports directory automatically
export SENTINEL_REPORTS_DIR="reports/$PROMPT_ID"
mkdir -p "$SENTINEL_REPORTS_DIR"

echo "======================================================================"
echo "PRISM Sentinel - Master Audit for Prompt: $PROMPT_ID"
echo "Reports will be written to: $SENTINEL_REPORTS_DIR/"
echo "======================================================================"

CMD="./scripts/run_sentinel_all.sh \"$TARGET_PROJECT\" --prompt-id \"$PROMPT_ID\""
if $WRITE_BQ; then
    CMD="$CMD --write-bq"
fi

eval $CMD
