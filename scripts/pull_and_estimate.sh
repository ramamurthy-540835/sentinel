#!/bin/bash
# Pull Prompt from GCS and Generate AI Estimation Report
set -euo pipefail

PROMPT_ID=${1:?ERROR: prompt_id required. Usage: ./pull_and_estimate.sh <prompt_id>}

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR/.."

echo "=================================================="
echo "PRISM PROMPT PULLER & AI ESTIMATOR"
echo "=================================================="
echo "Prompt ID: $PROMPT_ID"
echo ""

# Activate virtualenv if present
if [ -d "venv" ]; then
    source venv/bin/activate
fi

python3 agents/gcs_prompt_puller_and_estimator.py --prompt-id "$PROMPT_ID"

echo ""
echo "=================================================="
echo "🟢 PULL AND ESTIMATION RUN COMPLETED"
echo "=================================================="
echo "Output files ready:"
echo "  AI Estimation Report:  saved_prompts/$PROMPT_ID/ai_estimation.md"
echo "  Claude-Ready Prompt:   saved_prompts/$PROMPT_ID/claude_prompt.md"
echo "=================================================="
