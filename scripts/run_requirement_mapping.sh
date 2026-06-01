#!/bin/bash
set -e
TARGET_PROJECT=${1:-/home/appadmin/projects/Ram_Projects/DiracDelta/gcloud_run}

REPORTS_DIR="${SENTINEL_REPORTS_DIR:-reports}"
export SENTINEL_REPORTS_DIR="$REPORTS_DIR"

python3 agents/requirement_mapper.py --target-project "$TARGET_PROJECT"
