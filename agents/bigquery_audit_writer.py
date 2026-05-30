#!/usr/bin/env python3
"""
PRISM Sentinel BigQuery Audit Writer

Writes local audit reports to GCS and BigQuery (ctoteam.prism_sentinel_audit).

- Never prints or stores secrets
- Generates UUIDs for all IDs
- Local reports always succeed even if BQ/GCS sync fails
- Uses only bq + gsutil CLIs (no extra Python deps beyond stdlib + subprocess)
"""

import argparse
import json
import os
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def parse_args():
    parser = argparse.ArgumentParser(description="PRISM Sentinel BigQuery Audit Writer")
    parser.add_argument('--target-project', required=True, help='Path to the audited target project')
    parser.add_argument('--audit-run-id', required=True, help='UUID for this audit run')
    parser.add_argument('--gcs-base-uri', required=True, help='GCS URI base, e.g. gs://agentproject/sentinel-audits/myproject/<run_id>/')
    parser.add_argument('--reports-dir', default='reports', help='Local reports directory')
    parser.add_argument('--prompt-id', default='', help='Original Saved Prompt ID this target was built from (optional)')
    return parser.parse_args()


def generate_uuid() -> str:
    return str(uuid.uuid4())


def run_cmd(cmd: List[str], check: bool = True, capture: bool = False) -> Optional[str]:
    """Run a shell command safely. Returns stdout if capture=True."""
    try:
        if capture:
            result = subprocess.run(cmd, check=check, capture_output=True, text=True)
            return result.stdout.strip()
        else:
            subprocess.run(cmd, check=check)
            return None
    except subprocess.CalledProcessError as e:
        print(f"Command failed: {' '.join(cmd)}", file=sys.stderr)
        if e.stdout:
            print(e.stdout, file=sys.stderr)
        if e.stderr:
            print(e.stderr, file=sys.stderr)
        if check:
            raise
        return None


def load_json_safe(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def compute_overall_score_and_status(reports_dir: Path) -> tuple[float, str]:
    """Aggregate score and status from existing reports."""
    score = 100.0
    status = "PASSED"

    # Code quality score (primary signal)
    cq = load_json_safe(reports_dir / "code_quality_report.json")
    if cq.get("quality_score") is not None:
        score = float(cq.get("quality_score", 100))

    # Critical findings reduce score and change status
    critical_count = 0
    major_count = 0

    gap = load_json_safe(reports_dir / "gap_analysis.json")
    for g in gap.get("gaps", []):
        sev = g.get("severity", "").lower()
        if sev == "critical":
            critical_count += 1
        elif sev == "major":
            major_count += 1

    cq_findings = cq.get("findings", [])
    for f in cq_findings:
        sev = f.get("severity", "").lower()
        if sev == "critical":
            critical_count += 1
        elif sev == "major":
            major_count += 1

    # Penalize
    score = max(0.0, score - (critical_count * 15) - (major_count * 5))

    # Determine status
    if critical_count > 0:
        status = "CRITICAL_ISSUES"
    elif major_count > 0:
        status = "WARNINGS"
    else:
        status = "PASSED"

    return round(score, 1), status


def extract_findings(audit_run_id: str, reports_dir: Path) -> List[Dict[str, Any]]:
    """Flatten all findings from gap + code_quality reports."""
    findings = []
    now = datetime.now(timezone.utc).isoformat()

    # From gap_analysis
    gap = load_json_safe(reports_dir / "gap_analysis.json")
    for g in gap.get("gaps", []):
        findings.append({
            "finding_id": generate_uuid(),
            "audit_run_id": audit_run_id,
            "severity": g.get("severity", "info"),
            "category": g.get("category", "Gap"),
            "file_path": None,
            "line_number": None,
            "finding_text": g.get("description", ""),
            "recommendation": g.get("recommendation", ""),
            "owner_hint": g.get("owner_hint", ""),
            "created_at": now
        })

    # From code_quality_report
    cq = load_json_safe(reports_dir / "code_quality_report.json")
    for f in cq.get("findings", []):
        findings.append({
            "finding_id": generate_uuid(),
            "audit_run_id": audit_run_id,
            "severity": f.get("severity", "info"),
            "category": f.get("category", "Quality"),
            "file_path": f.get("file"),
            "line_number": None,
            "finding_text": f.get("description", ""),
            "recommendation": f.get("recommendation", ""),
            "owner_hint": f.get("owner_hint", ""),
            "created_at": now
        })

    return findings


def extract_traceability(audit_run_id: str, reports_dir: Path) -> List[Dict[str, Any]]:
    traces = []
    now = datetime.now(timezone.utc).isoformat()

    req = load_json_safe(reports_dir / "requirements_traceability.json")
    for item in req if isinstance(req, list) else []:
        evidence = item.get("evidence", [])
        impl_file = evidence[0]["file"] if evidence else None

        traces.append({
            "trace_id": generate_uuid(),
            "audit_run_id": audit_run_id,
            "requirement_id": item.get("requirement_id"),
            "requirement_text": item.get("description"),
            "implementation_file": impl_file,
            "test_file": None,
            "status": item.get("status", "Unknown"),
            "gap_text": "No implementation evidence found" if item.get("status") == "Missing" else None,
            "risk_level": "high" if item.get("status") == "Missing" else "low",
            "created_at": now
        })
    return traces


def build_artifact_rows(audit_run_id: str, reports_dir: Path, gcs_base: str) -> List[Dict[str, Any]]:
    artifacts = []
    now = datetime.now(timezone.utc).isoformat()

    report_files = [
        ("requirements_traceability.json", "report_json"),
        ("requirements_traceability.md", "report_md"),
        ("gap_analysis.json", "report_json"),
        ("gap_analysis.md", "report_md"),
        ("code_quality_report.json", "report_json"),
        ("code_quality_report.md", "report_md"),
        ("environment_validation.json", "report_json"),
        ("environment_validation.md", "report_md"),
        ("gcs_audit.json", "report_json"),
        ("gcs_audit.md", "report_md"),
        ("audit_evidence_package.md", "evidence_package"),
    ]

    for fname, atype in report_files:
        fpath = reports_dir / fname
        if fpath.exists():
            gcs_uri = f"{gcs_base.rstrip('/')}/{fname}"
            artifacts.append({
                "artifact_id": generate_uuid(),
                "audit_run_id": audit_run_id,
                "artifact_type": atype,
                "local_path": str(fpath),
                "gcs_uri": gcs_uri,
                "created_at": now
            })
    return artifacts


def write_ndjson(rows: List[Dict[str, Any]], path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def upload_to_gcs(local_reports: Path, gcs_base: str) -> bool:
    """Upload entire reports directory to GCS."""
    try:
        # Ensure gsutil exists
        run_cmd(["which", "gsutil"], check=True)
        cmd = ["gsutil", "-m", "cp", "-r", str(local_reports) + "/*", gcs_base]
        print(f"Uploading reports to {gcs_base} ...")
        run_cmd(cmd, check=True)
        print("GCS upload successful.")
        return True
    except Exception as e:
        print(f"GCS upload failed: {e}", file=sys.stderr)
        return False


def load_to_bigquery(table: str, ndjson_path: Path, project: str = "ctoteam") -> bool:
    """Load NDJSON into BigQuery table using bq CLI.
    Uses project:dataset.table syntax which works reliably across projects.
    """
    if not ndjson_path.exists() or ndjson_path.stat().st_size == 0:
        print(f"No data for {table}, skipping load.")
        return True

    try:
        full_table = f"{project}:prism_sentinel_audit.{table}"
        cmd = [
            "bq", "load",
            "--source_format=NEWLINE_DELIMITED_JSON",
            "--replace=false",
            full_table,
            str(ndjson_path)
        ]
        print(f"Loading {ndjson_path.name} into {full_table} ...")
        run_cmd(cmd, check=True)
        return True
    except Exception as e:
        print(f"BigQuery load failed for {table}: {e}", file=sys.stderr)
        return False


def main():
    args = parse_args()

    reports_dir = Path(args.reports_dir).resolve()
    target_path = Path(args.target_project).resolve()
    target_name = target_path.name
    audit_run_id = args.audit_run_id
    gcs_base = args.gcs_base_uri

    started = datetime.now(timezone.utc)
    print(f"PRISM Sentinel BigQuery Audit Writer starting for run {audit_run_id}")

    success = True
    overall_status = "COMPLETED"

    # 1. Compute overall metrics
    overall_score, overall_status = compute_overall_score_and_status(reports_dir)

    # 2. Prepare rows
    audit_run_row = {
        "audit_run_id": audit_run_id,
        "target_project_path": str(target_path),
        "target_project_name": target_name,
        "prompt_id": args.prompt_id or None,
        "overall_score": overall_score,
        "overall_status": overall_status,
        "started_at": started.isoformat(),
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "report_gcs_uri": gcs_base,
        "created_at": datetime.now(timezone.utc).isoformat()
    }

    findings_rows = extract_findings(audit_run_id, reports_dir)
    trace_rows = extract_traceability(audit_run_id, reports_dir)
    artifact_rows = build_artifact_rows(audit_run_id, reports_dir, gcs_base)

    # Write temporary load files
    tmp_dir = Path("/tmp/sentinel_audit") / audit_run_id
    write_ndjson([audit_run_row], tmp_dir / "audit_runs.ndjson")
    write_ndjson(findings_rows, tmp_dir / "audit_findings.ndjson")
    write_ndjson(trace_rows, tmp_dir / "requirement_traceability.ndjson")
    write_ndjson(artifact_rows, tmp_dir / "audit_artifacts.ndjson")

    # 3. Upload to GCS is handled by the calling shell script (write_audit_to_bigquery.sh)
    # We only do BigQuery metadata here. Mark GCS as already done.
    gcs_ok = True
    print("GCS upload assumed successful (performed by caller).")

    # 4. Load to BigQuery (best effort)
    if not load_to_bigquery("audit_runs", tmp_dir / "audit_runs.ndjson"):
        success = False
        overall_status = "BQ_SYNC_FAILED"

    if findings_rows and not load_to_bigquery("audit_findings", tmp_dir / "audit_findings.ndjson"):
        success = False
        overall_status = "BQ_SYNC_FAILED"

    if trace_rows and not load_to_bigquery("requirement_traceability", tmp_dir / "requirement_traceability.ndjson"):
        success = False
        overall_status = "BQ_SYNC_FAILED"

    if artifact_rows and not load_to_bigquery("audit_artifacts", tmp_dir / "audit_artifacts.ndjson"):
        success = False
        overall_status = "BQ_SYNC_FAILED"

    # Final status update if we had partial failure
    if not success and overall_status != "BQ_SYNC_FAILED":
        audit_run_row["overall_status"] = "BQ_SYNC_FAILED"
        # Re-load the run row with updated status
        write_ndjson([audit_run_row], tmp_dir / "audit_runs.ndjson")
        load_to_bigquery("audit_runs", tmp_dir / "audit_runs.ndjson")

    print(f"BigQuery audit writer finished. Overall status: {overall_status}")
    print(f"Reports available at: {gcs_base}")

    # Always succeed from Sentinel's perspective (local reports exist)
    # Only exit non-zero for unrecoverable Python errors (already handled by try/except in caller)
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Critical failure in bigquery_audit_writer: {e}", file=sys.stderr)
        sys.exit(1)
