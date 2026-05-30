#!/bin/bash
set -e
TARGET_PROJECT=${1:-/home/appadmin/projects/Ram_Projects/DiracDelta/gcloud_run}
python3 agents/gap_analyzer.py "$TARGET_PROJECT"
