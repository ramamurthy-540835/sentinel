#!/usr/bin/env python3
import os
import sys
import json
from pathlib import Path

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 gap_analyzer.py <target_project_path>")
        sys.exit(1)
        
    target_project = Path(sys.argv[1]).resolve()
    print(f"PRISM Sentinel Gap Analyzer starting on target: {target_project}")
    
    reports_dir = Path("reports")
    reports_dir.mkdir(exist_ok=True)
    
    # Load traceability matrix if available
    traceability_file = reports_dir / "requirements_traceability.json"
    traceability_data = []
    if traceability_file.exists():
        with open(traceability_file, "r") as f:
            traceability_data = json.load(f)
            
    gaps = []
    
    # 1. Check for missing requirement implementations
    for item in traceability_data:
        if item["status"] == "Missing":
            gaps.append({
                "category": "Missing Implementation",
                "severity": "critical",
                "description": f"Requirement {item['requirement_id']} has no mapped implementation evidence in the target project.",
                "recommendation": f"Implement logic for {item['requirement_id']} and reference the ID in code comments.",
                "owner_hint": "Lead Developer"
            })
            
    # 2. Check for missing tests
    test_files = list(target_project.glob("**/test_*.py")) + list(target_project.glob("**/*_test.py"))
    if not test_files:
        gaps.append({
            "category": "Missing Tests",
            "severity": "major",
            "description": "No Python test files (test_*.py or *_test.py) were found in the target project.",
            "recommendation": "Create a test suite under tests/ directory to verify core functionality.",
            "owner_hint": "QA Engineer"
        })
        
    # 3. Check for missing documentation
    readme_files = list(target_project.glob("**/README.md"))
    if not readme_files:
        gaps.append({
            "category": "Missing Documentation",
            "severity": "minor",
            "description": "No README.md file found in the target project root.",
            "recommendation": "Add a README.md explaining setup, architecture, and usage.",
            "owner_hint": "Technical Writer"
        })
        
    # 4. Check for missing configuration
    config_files = list(target_project.glob("**/.env*")) + list(target_project.glob("**/*.json")) + list(target_project.glob("**/*.yaml"))
    if not config_files:
        gaps.append({
            "category": "Missing Configuration",
            "severity": "major",
            "description": "No configuration files (.env, .json, .yaml) found in the target project.",
            "recommendation": "Add standard configuration templates or environment files.",
            "owner_hint": "DevOps Engineer"
        })

    # Write Markdown report
    md_report_path = reports_dir / "gap_analysis.md"
    with open(md_report_path, "w") as f:
        f.write("# PRISM Sentinel - Gap Analysis Report\n\n")
        f.write("## Execution Plan & Reasoning Summary\n")
        f.write("Analyzed target project structure and compared it against extracted requirements to identify missing components, tests, documentation, and configurations.\n\n")
        
        if not gaps:
            f.write("### ✅ No Gaps Identified\n")
            f.write("The target project meets all basic structural and requirement mapping criteria.\n")
        else:
            f.write("## Identified Gaps\n\n")
            f.write("| Category | Severity | Description | Recommendation | Owner Hint |\n")
            f.write("| --- | --- | --- | --- | --- |\n")
            for gap in gaps:
                sev_emoji = "🔴" if gap["severity"] == "critical" else "orange_circle" if gap["severity"] == "major" else "yellow_circle"
                sev_emoji = "🔴" if gap["severity"] == "critical" else "🟠" if gap["severity"] == "major" else "🟡" if gap["severity"] == "minor" else "🔵"
                f.write(f"| {gap['category']} | {sev_emoji} {gap['severity'].upper()} | {gap['description']} | {gap['recommendation']} | {gap['owner_hint']} |\n")
                
    print(f"Gap analysis report generated successfully in {reports_dir}/")

if __name__ == "__main__":
    main()
