#!/usr/bin/env python3
import os
import sys
import py_compile
import subprocess
import re
from pathlib import Path

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 code_quality_reviewer.py <target_project_path>")
        sys.exit(1)
        
    target_project = Path(sys.argv[1]).resolve()
    print(f"PRISM Sentinel Code Quality Reviewer starting on target: {target_project}")
    
    reports_dir = Path("reports")
    reports_dir.mkdir(exist_ok=True)
    
    findings = []
    total_checks = 0
    passed_checks = 0
    
    # 1. Python Compile Check
    python_files = list(target_project.glob("**/*.py"))
    for py_file in python_files:
        total_checks += 1
        try:
            py_compile.compile(str(py_file), doraise=True)
            passed_checks += 1
        except py_compile.PyCompileError as e:
            findings.append({
                "category": "Python Compilation",
                "severity": "critical",
                "file": str(py_file.relative_to(target_project)),
                "description": f"Python compilation failed: {e}",
                "recommendation": "Fix syntax errors in the Python file.",
                "owner_hint": "Developer"
            })

    # 2. Bash Syntax Check (using bash -n)
    sh_files = list(target_project.glob("**/*.sh"))
    for sh_file in sh_files:
        total_checks += 1
        res = subprocess.run(["bash", "-n", str(sh_file)], capture_output=True, text=True)
        if res.returncode != 0:
            findings.append({
                "category": "Bash Syntax",
                "severity": "major",
                "file": str(sh_file.relative_to(target_project)),
                "description": f"Bash syntax check failed: {res.stderr.strip()}",
                "recommendation": "Fix shell script syntax errors.",
                "owner_hint": "DevOps Engineer"
            })
        else:
            passed_checks += 1

    # 3. SQL Scan & Forbidden Model Scan & Secret Scan
    forbidden_models = ["gemini-1.5", "gemini-2.0", "gemini-2.5"]
    secret_patterns = ["AI_PROVIDER", "GITHUB_TOKEN", "PASSWORD", "SECRET_KEY", "PRIVATE_KEY"]
    
    for root, _, files in os.walk(target_project):
        for file in files:
            file_path = Path(root) / file
            if file_path.suffix in [".py", ".sh", ".sql", ".json", ".env", ".local", ".md"]:
                try:
                    content = file_path.read_text(errors="ignore")
                    rel_path = file_path.relative_to(target_project)
                    
                    # SQL Scan
                    if file_path.suffix == ".sql":
                        total_checks += 1
                        if "select *" in content.lower():
                            findings.append({
                                "category": "SQL Scan",
                                "severity": "minor",
                                "file": str(rel_path),
                                "description": "Use of 'SELECT *' detected. Explicit column selection is preferred.",
                                "recommendation": "Replace 'SELECT *' with explicit column names.",
                                "owner_hint": "Data Engineer"
                            })
                        else:
                            passed_checks += 1
                            
                    # Forbidden Model Scan
                    for model in forbidden_models:
                        total_checks += 1
                        if model in content:
                            findings.append({
                                "category": "Forbidden Model Policy",
                                "severity": "critical",
                                "file": str(rel_path),
                                "description": f"Forbidden model '{model}' referenced in file.",
                                "recommendation": "Migrate to allowed models: gemini-3.5-flash, grok-4.2-reasoning, or grok-4.2-non-reasoning.",
                                "owner_hint": "Architect"
                            })
                        else:
                            passed_checks += 1
                            
                    # Secret Scan (Check if actual secrets are hardcoded, ignoring template/env files themselves)
                    if file_path.suffix not in [".env", ".local"]:
                        for pattern in secret_patterns:
                            total_checks += 1
                            # Simple heuristic: pattern followed by equals and a non-empty value
                            match = re.search(rf"{pattern}\s*=\s*['\"]?([^'\"\s]+)['\"]?", content, re.IGNORECASE)
                            if match and not match.group(1).startswith(("$", "{")):
                                findings.append({
                                    "category": "Secret Leak Prevention",
                                    "severity": "critical",
                                    "file": str(rel_path),
                                    "description": f"Potential hardcoded secret/credential '{pattern}' detected.",
                                    "recommendation": "Move secrets to environment variables or secret manager.",
                                    "owner_hint": "Security Engineer"
                                })
                            else:
                                passed_checks += 1
                except Exception:
                    pass

    # Calculate Quality Score
    score = int((passed_checks / total_checks) * 100) if total_checks > 0 else 100
    
    # Write Markdown report
    md_report_path = reports_dir / "code_quality_report.md"
    with open(md_report_path, "w") as f:
        f.write("# PRISM Sentinel - Code Quality Report\n\n")
        f.write("## Execution Plan & Reasoning Summary\n")
        f.write("Performed static analysis checks including Python compilation, Bash syntax validation, SQL best practices, forbidden model policy compliance, and hardcoded secret scanning.\n\n")
        f.write(f"### Quality Score: {score}/100\n")
        f.write(f"Passed {passed_checks} out of {total_checks} checks.\n\n")
        
        if not findings:
            f.write("### ✅ No Quality Issues Found\n")
        else:
            f.write("## Quality Findings\n\n")
            f.write("| Category | Severity | File | Description | Recommendation | Owner Hint |\n")
            f.write("| --- | --- | --- | --- | --- |\n")
            for finding in findings:
                sev_text = f"🔴 {finding['severity'].upper()}" if finding["severity"] == "critical" else f"🟠 {finding['severity'].upper()}" if finding["severity"] == "major" else f"🟡 {finding['severity'].upper()}"
                f.write(f"| {finding['category']} | {sev_text} | {finding['file']} | {finding['description']} | {finding['recommendation']} | {finding['owner_hint']} |\n")
                
    print(f"Code quality report generated successfully in {reports_dir}/")

if __name__ == "__main__":
    main()
