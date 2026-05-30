#!/bin/bash
# PRISM Prompt-ID Coding Agent - Regression & Smoke Test
set -euo pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR/.."

echo "=================================================="
echo "PRISM PROMPT-ID AGENT: SMOKE TEST RUN"
echo "=================================================="
echo "Target: $PWD"
echo ""

# 1. Verify Syntax Compilation
echo "[STEP 1] Checking Python Syntax Compilation..."
python3 -m py_compile agents/prompt_id_coder_agent.py
echo "✓ Code compilation successful."
echo ""

# 2. Run dry-run against standard prompt dataset
echo "[STEP 2] Running Dry-Run Extraction for Prompt ID 2114685765899255808..."
python3 agents/prompt_id_coder_agent.py --prompt-id 2114685765899255808 --dry-run
echo ""

# 3. Assert local files are generated correctly with full fidelity
echo "[STEP 3] Verifying Generated Artifacts..."
TARGET_DIR="saved_prompts/2114685765899255808"

if [ -d "$TARGET_DIR" ]; then
    echo "✓ Target directory exists: $TARGET_DIR"
else
    echo "❌ ERROR: Target directory missing: $TARGET_DIR"
    exit 1
fi

# List of mandatory files in standard prompt packaging format
MANDATORY_FILES=(
    "raw.json"
    "system.md"
    "extracted_content.txt"
    "chunk_001.md"
    "final_assembled.md"
    "master.md"
    "index.json"
)

for file in "${MANDATORY_FILES[@]}"; do
    FILE_PATH="$TARGET_DIR/$file"
    if [ -f "$FILE_PATH" ]; then
        SIZE=$(wc -c < "$FILE_PATH" | tr -d ' ')
        echo "  ✓ File verified: $file ($SIZE bytes)"
    else
        echo "❌ ERROR: Mandatory file missing: $file"
        exit 1
    fi
done

echo ""
echo "=================================================="
echo "🟢 REGRESSION SMOKE TEST PASSED SUCCESSFULLY"
echo "=================================================="
