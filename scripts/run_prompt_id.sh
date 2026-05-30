#!/bin/bash
set -e

PROMPT_ID=${1:?Usage: ./scripts/run_prompt_id.sh <prompt_id> [--run-aider]}
RUN_AIDER=${2:-}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$SCRIPT_DIR"

echo "╔════════════════════════════════════════════╗"
echo "║  PROMPT-ID AGENT                           ║"
echo "╚════════════════════════════════════════════╝"
echo ""
echo "Prompt ID: $PROMPT_ID"
echo "Directory: $(pwd)"
echo ""

[ -f "venv/bin/activate" ] && source venv/bin/activate

CMD="python3 agents/prompt_id_coder_agent.py --prompt-id $PROMPT_ID"
[ "$RUN_AIDER" = "--run-aider" ] && CMD="$CMD --run-aider"

eval "$CMD"
