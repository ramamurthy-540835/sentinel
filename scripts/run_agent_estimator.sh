#!/bin/bash
# PRISM Agent 2: AI Estimator with Gemini 3.5 Flash
set -euo pipefail

PROMPT_ID=${1:?ERROR: prompt_id required}
MODEL=${2:-gemini-3.5-flash}
PROJECT=${3:-ctoteam}
LOCATION=${4:-us-central1}

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR/.."

echo "=================================================="
echo "PRISM AGENT 2: AI ESTIMATOR"
echo "=================================================="
echo "Prompt ID: $PROMPT_ID"
echo "Model:     $MODEL"
echo "Project:   $PROJECT"
echo "Location:  $LOCATION"
echo ""

if [ -d "venv" ]; then
    source venv/bin/activate
fi

python3 agents/agent_ai_estimator.py \
    --prompt-id "$PROMPT_ID" \
    --model "$MODEL" \
    --project-id "$PROJECT" \
    --location "$LOCATION"

echo ""
echo "🟢 AI Estimator completed (tokens logged to BigQuery)"
echo "=================================================="
