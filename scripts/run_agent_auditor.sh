#!/bin/bash
# PRISM Agent 4: Code Quality & Token Audit Agent
set -euo pipefail

PROMPT_ID=${1:?ERROR: prompt_id required}

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR/.."

echo "=================================================="
echo "PRISM AGENT 4: CODE QUALITY & TOKEN AUDITOR"
echo "=================================================="
echo "Prompt ID: $PROMPT_ID"
echo ""

if [ -d "venv" ]; then
    source venv/bin/activate
fi

python3 agents/agent_code_quality_auditor.py --prompt-id "$PROMPT_ID"

echo ""
echo "🟢 Code Quality Audit completed"
echo "=================================================="
