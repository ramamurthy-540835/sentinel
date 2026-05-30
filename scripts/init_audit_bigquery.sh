#!/bin/bash
# Initialize PRISM Sentinel Audit BigQuery dataset and tables
# Usage: ./scripts/init_audit_bigquery.sh

set -euo pipefail

PROJECT="ctoteam"
DATASET="prism_sentinel_audit"
LOCATION="us-central1"

echo "================================================================================"
echo "PRISM Sentinel - Initialize BigQuery Audit Catalog"
echo "Dataset: ${PROJECT}.${DATASET}"
echo "================================================================================"

# Create dataset (idempotent)
if bq ls --project_id="${PROJECT}" | grep -q "${DATASET}"; then
    echo "Dataset ${PROJECT}:${DATASET} already exists."
else
    echo "Creating dataset ${PROJECT}:${DATASET}..."
    bq --location="${LOCATION}" mk --dataset \
        --description="PRISM Sentinel audit results, findings, traceability and artifacts" \
        "${PROJECT}:${DATASET}"
fi

# Create tables from SQL
echo ""
echo "Creating/ensuring tables..."
bq query --use_legacy_sql=false --project_id="${PROJECT}" \
    --nouse_cache \
    < sql/sentinel_audit/create_tables.sql

echo ""
echo "✅ BigQuery audit catalog initialized."
echo ""
echo "Tables in ${PROJECT}.${DATASET}:"
bq ls --project_id="${PROJECT}" "${DATASET}"

echo ""
echo "You can now run audits with --write-bq"
echo "================================================================================"
