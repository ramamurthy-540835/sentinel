#!/bin/bash
# Extract and chunk a Vertex AI saved prompt dataset
# Usage: ./scripts/extract_prompt_chunks.sh <prompt_id> [--chunk-size 15000] [--chunk-overlap 1500]

set -e

PROMPT_ID=${1:-7562985783854891008}
CHUNK_SIZE=${2:-15000}
CHUNK_OVERLAP=${3:-1500}

echo "Extracting prompt: $PROMPT_ID"
echo "Chunk size: $CHUNK_SIZE, overlap: $CHUNK_OVERLAP"

source venv/bin/activate
python3 agents/read_saved_prompt_chunked.py \
  --prompt-id "$PROMPT_ID" \
  --chunk-size "$CHUNK_SIZE" \
  --chunk-overlap "$CHUNK_OVERLAP" \
  --deterministic-only

echo ""
echo "✓ Chunks created in: saved_prompts/$PROMPT_ID/"
echo "✓ Run: aider saved_prompts/$PROMPT_ID/master.md"
