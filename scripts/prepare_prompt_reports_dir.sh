#!/bin/bash
# Usage:
#   source scripts/prepare_prompt_reports_dir.sh <prompt_id>
#   or
#   REPORTS_DIR=$(./scripts/prepare_prompt_reports_dir.sh <prompt_id>)

set -euo pipefail

PROMPT_ID="${1:-}"

if [[ -z "$PROMPT_ID" ]]; then
    echo "Usage: $0 <prompt_id>" >&2
    echo "   or: source $0 <prompt_id>" >&2
    exit 1
fi

REPORTS_DIR="reports/${PROMPT_ID}"
mkdir -p "${REPORTS_DIR}"

# Export for child processes / python agents
export SENTINEL_REPORTS_DIR="${REPORTS_DIR}"

# If sourced, also set a local var the caller can use
if [[ "${BASH_SOURCE[0]}" != "${0}" ]]; then
    # Being sourced
    echo "SENTINEL_REPORTS_DIR=${REPORTS_DIR}" >&2
else
    # Being executed directly → print the path
    echo "${REPORTS_DIR}"
fi
