#!/bin/bash
# PRISM Agent 3: Code Developer
set -euo pipefail

PROMPT_ID=${1:?ERROR: prompt_id required}
MODEL=${2:-gemini-3.5-flash}

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR/.."

echo "=================================================="
echo "PRISM AGENT 3: CODE DEVELOPER"
echo "=================================================="
echo "Prompt ID: $PROMPT_ID"
echo "Model:     $MODEL"
echo ""

if [ -d "venv" ]; then
    source venv/bin/activate
fi

python3 agents/agent_code_developer.py \
    --prompt-id "$PROMPT_ID" \
    --model "$MODEL"

echo ""
echo "🟢 Code Developer completed"
echo "=================================================="
