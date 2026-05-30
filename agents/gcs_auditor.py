#!/usr/bin/env python3
import os
import sys
from pathlib import Path

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 gcs_auditor.py <target_project_path>")
        sys.exit(1)
        
    target_project = Path(sys.argv[1]).resolve()
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

if __name__ == "__main__":
    main()
