#!/bin/bash
# PRISM Agent Orchestrator: Runs all 3 agents in sequence
set -euo pipefail

PROMPT_ID=${1:?ERROR: prompt_id required}
MODEL=${2:-gemini-3.5-flash-001}
BUCKET=${3:-agentproject}

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR/.."

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║          PRISM AGENT ORCHESTRATOR - FULL PIPELINE              ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "Configuration:"
echo "  Prompt ID: $PROMPT_ID"
echo "  Model:     $MODEL"
echo "  Bucket:    $BUCKET"
echo ""

# Agent 1: GCS Prompt Puller
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "▶ AGENT 1: GCS PROMPT PULLER"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
bash scripts/run_agent_puller.sh "$PROMPT_ID" "$BUCKET"
if [ $? -ne 0 ]; then
    echo "❌ Agent 1 failed!"
    exit 1
fi

sleep 2

# Agent 2: AI Estimator
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "▶ AGENT 2: AI ESTIMATOR (Gemini 3.5 Flash)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
bash scripts/run_agent_estimator.sh "$PROMPT_ID" "$MODEL"
if [ $? -ne 0 ]; then
    echo "❌ Agent 2 failed!"
    exit 1
fi

sleep 2

# Agent 3: Code Developer
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "▶ AGENT 3: CODE DEVELOPER"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
bash scripts/run_agent_developer.sh "$PROMPT_ID" "$MODEL"

sleep 2

# Agent 4: Code Quality & Token Auditor
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "▶ AGENT 4: CODE QUALITY & TOKEN AUDITOR"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
bash scripts/run_agent_auditor.sh "$PROMPT_ID"

# Final summary
echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║            🟢 ALL AGENTS COMPLETED SUCCESSFULLY                ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "Output Directory: saved_prompts/$PROMPT_ID/"
echo ""
echo "Generated Files:"
echo "  ✓ system_instructions.md        (System rules)"
echo "  ✓ assembled_requirements.md     (Full requirements)"
echo "  ✓ ai_estimation.md              (Architecture & WBS)"
echo "  ✓ token_stats.json              (Gemini token usage)"
echo "  ✓ run_metadata.json             (Run metadata)"
echo ""
echo "Next Steps: Push to GCS development folder or deploy to 10.100.15.31"
echo ""
