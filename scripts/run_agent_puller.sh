#!/bin/bash
# PRISM Agent 1: GCS Prompt Puller
set -euo pipefail

PROMPT_ID=${1:?ERROR: prompt_id required}
BUCKET=${2:-agentproject}

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR/.."

echo "=================================================="
echo "PRISM AGENT 1: GCS PROMPT PULLER"
echo "=================================================="
echo "Prompt ID: $PROMPT_ID"
echo "Bucket:    $BUCKET"
echo ""

if [ -d "venv" ]; then
    source venv/bin/activate
fi

python3 agents/agent_gcs_puller.py --prompt-id "$PROMPT_ID" --bucket "$BUCKET"

echo ""
echo "🟢 GCS Prompt Puller completed"
echo "=================================================="
