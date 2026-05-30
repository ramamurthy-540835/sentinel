#!/bin/bash
# Run BQML-assisted Requirement Scope Extraction
# Usage: ./scripts/run_requirement_scope_extraction.sh <prompt_id>

set -euo pipefail

PROMPT_ID=${1:?ERROR: prompt_id required (e.g. 3381323161097207808)}

echo "================================================================================"
echo "PRISM Sentinel - BQML Requirement Scope Extraction"
echo "Prompt ID: $PROMPT_ID"
echo "================================================================================"

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR/.."

python3 agents/bqml_requirement_scope.py "$PROMPT_ID"

echo ""
echo "================================================================================"
echo "Requirement scope extraction complete."
echo "Reports available in: reports/$PROMPT_ID/"
echo "  - requirement_scope_clean.md"
echo "  - requirement_scope_clean.json"
echo "  - noise_classification_report.md"
echo "================================================================================"