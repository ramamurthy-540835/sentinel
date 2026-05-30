#!/bin/bash
set -e

TARGET_PROJECT=${1:-/home/appadmin/projects/Ram_Projects/DiracDelta/gcloud_run}

echo "================================================================================"
echo "PRISM Sentinel Quality Agent - Full Audit Execution"
echo "Target Project: $TARGET_PROJECT"
echo "================================================================================"

mkdir -p reports

echo "1. Running Requirement Mapping..."
./scripts/run_requirement_mapping.sh "$TARGET_PROJECT"

echo "2. Running Gap Analysis..."
./scripts/run_gap_analysis.sh "$TARGET_PROJECT"

echo "3. Running Code Quality Review..."
./scripts/run_code_quality.sh "$TARGET_PROJECT"

echo "4. Running Environment Validation..."
./scripts/run_env_validation.sh "$TARGET_PROJECT"

echo "5. Running GCS Audit..."
./scripts/run_gcs_audit.sh "$TARGET_PROJECT"

echo "6. Packaging Audit Evidence..."
./scripts/run_audit_package.sh "$TARGET_PROJECT"

echo "================================================================================"
echo "PRISM Sentinel Audit Complete! All reports generated under reports/"
echo "================================================================================"
