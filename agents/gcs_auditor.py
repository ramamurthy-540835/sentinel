#!/usr/bin/env python3
import os
import sys
import json
import argparse
from pathlib import Path

def parse_args():
    parser = argparse.ArgumentParser(description="PRISM Sentinel GCS Auditor")
    parser.add_argument('--target-project', type=str, help='Path to target project')
    parser.add_argument('positional_target', nargs='?', type=str, help='Path to target project (positional)')
    args = parser.parse_args()
    
    target = args.target_project or args.positional_target
    if not target:
        print("Error: Target project path is required. Use --target-project <path> or pass it as a positional argument.", file=sys.stderr)
        sys.exit(1)
    return Path(target).resolve()

def main():
    try:
        target_project = parse_args()
        print(f"PRISM Sentinel GCS Auditor starting on target: {target_project}")
        
        reports_dir = Path("reports")
        reports_dir.mkdir(exist_ok=True)
        
        findings = []
        
        # Check for GCS layout references in code/config
        gcs_references = []
        for root, _, files in os.walk(target_project):
            for file in files:
                file_path = Path(root) / file
                if file_path.suffix in [".py", ".sh", ".sql", ".json", ".yaml", ".yml"]:
                    try:
                        content = file_path.read_text(errors="ignore")
                        if "gs://" in content:
                            gcs_references.append({
                                "file": str(file_path.relative_to(target_project)),
                                "content": [line.strip() for line in content.splitlines() if "gs://" in line]
                            })
                    except Exception:
                        pass
                        
        # Check for bronze/silver/gold layout references
        has_medallion_layout = False
        for ref in gcs_references:
            for line in ref["content"]:
                if any(layer in line.lower() for layer in ["bronze", "silver", "gold"]):
                    has_medallion_layout = True
                    break
                    
        if not gcs_references:
            findings.append({
                "category": "GCS Layout",
                "severity": "info",
                "description": "No GCS bucket references (gs://) found in the target project.",
                "recommendation": "If GCS is used, define bucket paths in configuration files.",
                "owner_hint": "Data Engineer"
            })
        elif not has_medallion_layout:
            findings.append({
                "category": "GCS Layout",
                "severity": "minor",
                "description": "GCS references found, but no standard Medallion (Bronze/Silver/Gold) layout detected.",
                "recommendation": "Adopt Medallion architecture layout for structured data pipelines.",
                "owner_hint": "Data Architect"
            })

        # Write JSON report
        json_report_path = reports_dir / "gcs_audit.json"
        with open(json_report_path, "w") as f:
            json.dump({"gcs_references": gcs_references, "findings": findings}, f, indent=2)

        # Write Markdown report
        md_report_path = reports_dir / "gcs_audit.md"
        with open(md_report_path, "w") as f:
            f.write("# PRISM Sentinel - GCS Audit Report\n\n")
            f.write("## Execution Plan & Reasoning Summary\n")
            f.write("Audited target project files for GCS bucket references and verified compliance with standard Medallion architecture layouts.\n\n")
            
            if not findings:
                f.write("### ✅ GCS Layout Audit Passed\n")
            else:
                f.write("## Audit Findings\n\n")
                f.write("| Category | Severity | Description | Recommendation | Owner Hint |\n")
                f.write("| --- | --- | --- | --- | --- |\n")
                for finding in findings:
                    sev_text = f"🟡 {finding['severity'].upper()}" if finding["severity"] == "minor" else f"🔵 {finding['severity'].upper()}"
                    f.write(f"| {finding['category']} | {sev_text} | {finding['description']} | {finding['recommendation']} | {finding['owner_hint']} |\n")
                    
        print(f"GCS audit report generated successfully in {reports_dir}/")
    except Exception as e:
        print(f"Critical failure in GCS auditor: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
