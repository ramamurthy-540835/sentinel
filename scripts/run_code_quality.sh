#!/bin/bash
set -e
TARGET_PROJECT=${1:-/home/appadmin/projects/Ram_Projects/DiracDelta/gcloud_run}

# Respect per-prompt reports directory if set by orchestrator or user
REPORTS_DIR="${SENTINEL_REPORTS_DIR:-reports}"
export SENTINEL_REPORTS_DIR="$REPORTS_DIR"

python3 agents/code_quality_reviewer.py --target-project "$TARGET_PROJECT"
