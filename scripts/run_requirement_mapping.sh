#!/bin/bash
set -e
TARGET_PROJECT=${1:-/home/appadmin/projects/Ram_Projects/DiracDelta/gcloud_run}
python3 agents/requirement_mapper.py "$TARGET_PROJECT"
