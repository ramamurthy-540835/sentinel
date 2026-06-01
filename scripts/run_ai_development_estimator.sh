#!/bin/bash
#
# PRISM Sentinel - Scientific AI Development Estimator (Gemini 3.5 Flash)
# Thin orchestrator wrapper. All logic lives in agents/ai_development_estimator.py
#
# Usage (exactly as specified):
#   ./scripts/run_ai_development_estimator.sh 3381323161097207808 ../coder
#
# The estimator implements:
#   - BigQuery prompt_registry (when present) → GCS → local fallbacks
#   - Deterministic requirement extraction + IFPUG-style FP scoring
#   - Phase-based token estimation with complexity iteration multipliers
#   - Low-cost optimization recommendations
#   - Validation against actual code in the target project
#

set -euo pipefail

PROMPT_ID="${1:?ERROR: prompt_id is required (e.g. 3381323161097207808)}"
TARGET_DIR="${2:?ERROR: target_dir is required (e.g. ../coder)}"

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
SENTINEL_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

echo "================================================================================"
echo "🚀 PRISM Sentinel - Scientific AI Development Estimator"
echo "================================================================================"
echo "Prompt ID      : $PROMPT_ID"
echo "Target Project : $TARGET_DIR (relative to sentinel root)"
echo "Working Dir    : $SENTINEL_ROOT"
echo "================================================================================"
echo ""

cd "$SENTINEL_ROOT"

# Ensure reports directory exists for this prompt
mkdir -p "reports/${PROMPT_ID}"

# Execute the core Python implementation
echo "[1/2] Running estimator..."
python3 agents/ai_development_estimator.py "$PROMPT_ID" "$TARGET_DIR"

EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    echo ""
    echo "================================================================================"
    echo "❌ Estimator exited with code $EXIT_CODE"
    echo "================================================================================"
    exit $EXIT_CODE
fi

# Persist results to BigQuery
echo ""
echo "[2/2] Persisting results to BigQuery..."
python3 agents/persist_estimation_to_bigquery.py "$PROMPT_ID"

PERSIST_EXIT=$?

echo ""
echo "================================================================================"
if [ $PERSIST_EXIT -eq 0 ]; then
    echo "✅ Estimation complete and persisted."
    echo ""
    echo "Reports written to:"
    echo "  reports/${PROMPT_ID}/scientific_estimation.md"
    echo "  reports/${PROMPT_ID}/scientific_estimation.json"
    echo ""
    echo "Key artifacts for prompt ${PROMPT_ID}:"
    ls -lh "reports/${PROMPT_ID}/scientific_estimation."* 2>/dev/null || true
else
    echo "❌ BigQuery persistence exited with code $PERSIST_EXIT"
fi
echo "================================================================================"

exit $PERSIST_EXIT
