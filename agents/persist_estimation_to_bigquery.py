#!/usr/bin/env python3
"""
Persist Scientific Estimation Results to BigQuery

Reads the JSON estimation report and writes it to:
  ctoteam.prism_sentinel_estimation.ai_development_estimates

Usage:
  python3 agents/persist_estimation_to_bigquery.py 3381323161097207808
"""

import json
import sys
from pathlib import Path
from datetime import datetime, timezone
from google.cloud import bigquery

def main(prompt_id: str):
    """Load estimation JSON and write to BigQuery."""

    # Read the estimation JSON
    report_path = Path(f"reports/{prompt_id}/scientific_estimation.json")
    if not report_path.exists():
        print(f"❌ Report not found: {report_path}")
        sys.exit(1)

    with open(report_path, 'r', encoding='utf-8') as f:
        estimation = json.load(f)

    # Initialize BigQuery client
    client = bigquery.Client(project='ctoteam')
    table = client.get_table('ctoteam.prism_sentinel_estimation.ai_development_estimates')

    # Extract key fields from estimation
    result_row = {
        'estimation_run_uuid': estimation.get('estimation_run_uuid'),
        'prompt_id': estimation.get('prompt_id'),
        'target_project': estimation.get('target_project', 'unknown'),
        'total_functional_points': float(
            estimation.get('functional_points', {}).get('total_functional_points', 0)
        ),
        'complexity_band': estimation.get('functional_points', {}).get('complexity_band'),
        'estimated_input_tokens': int(
            estimation.get('token_estimate', {}).get('total_estimated_input_tokens', 0)
        ),
        'estimated_output_tokens': int(
            estimation.get('token_estimate', {}).get('total_estimated_output_tokens', 0)
        ),
        'estimated_total_tokens': int(
            estimation.get('token_estimate', {}).get('estimated_total_tokens', 0)
        ),
        'estimated_total_cost_usd': float(
            estimation.get('token_estimate', {}).get('estimated_total_cost_usd', 0)
        ),
        'model_used': estimation.get('model'),
        'source_file': str(report_path),
        'source_type': estimation.get('source_type'),
        'source_quality_score': float(estimation.get('source_quality_score', 0.0)),
        'created_at': datetime.now(timezone.utc).isoformat(),
        'raw_json': json.dumps(estimation)
    }

    # Write to BigQuery
    try:
        errors = client.insert_rows_json(
            table,
            [result_row],
            row_ids=[estimation.get('estimation_run_uuid')]
        )

        if errors:
            print(f"❌ BigQuery insert errors: {errors}")
            sys.exit(1)

        print(f"✅ Estimation persisted to BigQuery")
        print(f"   UUID: {result_row['estimation_run_uuid']}")
        print(f"   FP: {result_row['total_functional_points']}")
        print(f"   Tokens: {result_row['estimated_total_tokens']:,}")
        print(f"   Cost: ${result_row['estimated_total_cost_usd']:.2f}")
        print(f"   Source: {result_row['source_type']} ({result_row['source_quality_score']:.0%})")

    except Exception as e:
        print(f"❌ Failed to write to BigQuery: {e}")
        sys.exit(1)

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python3 persist_estimation_to_bigquery.py <prompt_id>")
        sys.exit(1)

    main(sys.argv[1])
