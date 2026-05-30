#!/bin/bash
set -e
TARGET_PROJECT=${1:-/home/appadmin/projects/Ram_Projects/DiracDelta/gcloud_run}
python3 agents/audit_packager.py --target-project "$TARGET_PROJECT"
