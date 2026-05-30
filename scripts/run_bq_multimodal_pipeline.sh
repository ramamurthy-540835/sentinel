#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "[1/4] Create connection + model"
bq query --use_legacy_sql=false < sql/prompt_catalog/10_bq_connection_model.sql

echo "[2/4] Create object table"
bq query --use_legacy_sql=false < sql/prompt_catalog/11_object_table.sql

echo "[3/4] Extract multimodal text"
bq query --use_legacy_sql=false < sql/prompt_catalog/12_extract_multimodal.sql

echo "[4/4] Create gold view"
bq query --use_legacy_sql=false < sql/prompt_catalog/13_gold_multimodal_view.sql

echo "Done. Validate with:"
echo "bq query --use_legacy_sql=false 'SELECT * FROM `ctoteam.prism_prompt_catalog.gold_multimodal_attachments` LIMIT 20'"
