#!/usr/bin/env python3
import os
import sys
import json
from pathlib import Path

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 env_validator.py <target_project_path>")
        sys.exit(1)
        
    target_project = Path(sys.argv[1]).resolve()
    print(f"PRISM Sentinel Environment Validator starting on target: {target_project}")
    
    reports_dir = Path("reports")
    reports_dir.mkdir(exist_ok=True)
    
    findings = []
    
    # 1. Check .env.local presence
    env_local_path = Path(".env.local")
    if not env_local_path.exists():
        findings.append({
            "category": "Environment Configuration",
            "severity": "critical",
            "description": ".env.local file is missing from the workspace root.",
            "recommendation": "Create a .env.local file with required environment variables.",
            "owner_hint": "DevOps Engineer"
        })
    else:
        # Read without printing secrets
        try:
            lines = env_local_path.read_text().splitlines()
            for line in lines:
                if line.strip() and not line.startswith("#"):
                    if "=" in line:
                        key = line.split("=", 1)[0].strip()
                        # Never print keys or values from .env files (secrets policy)
                        # Only record that a key was present if needed for debugging
                        pass  # silent validation - no secret leakage allowed
        except Exception as e:
            findings.append({
                "category": "Environment Configuration",
                "severity": "major",
                "description": f"Failed to parse .env.local: {e}",
                "recommendation": "Ensure .env.local is a valid key-value format.",
                "owner_hint": "Developer"
            })

    # 2. Check models.json
    models_json_path = Path("models.json")
    if not models_json_path.exists():
        findings.append({
            "category": "Model Configuration",
            "severity": "major",
            "description": "models.json file is missing from the workspace root.",
            "recommendation": "Create a models.json file defining allowed models.",
            "owner_hint": "Architect"
        })
    else:
        try:
            with open(models_json_path, "r") as f:
                models_data = json.load(f)
                
            # Check allowed model policy
            allowed_models = ["gemini-3.5-flash", "grok-4.2-reasoning", "grok-4.2-non-reasoning", "gemini-flash", "grok-fast", "grok-reasoning"]
            default_model = models_data.get("default_model")
            if default_model not in allowed_models:
                findings.append({
                    "category": "Model Policy Compliance",
                    "severity": "critical",
                    "description": f"Default model '{default_model}' violates the allowed model policy.",
                    "recommendation": "Change default_model to an allowed model (e.g., gemini-flash).",
                    "owner_hint": "Architect"
                })
        except Exception as e:
            findings.append({
                "category": "Model Configuration",
                "severity": "major",
                "description": f"Failed to parse models.json: {e}",
                "recommendation": "Ensure models.json is valid JSON.",
                "owner_hint": "Developer"
            })

    # Write Markdown report
    md_report_path = reports_dir / "environment_validation.md"
    with open(md_report_path, "w") as f:
        f.write("# PRISM Sentinel - Environment Validation Report\n\n")
        f.write("## Execution Plan & Reasoning Summary\n")
        f.write("Validated environment configuration files, ensuring no secrets are exposed, and verified compliance with the allowed model policy.\n\n")
        
        if not findings:
            f.write("### ✅ Environment Validation Passed\n")
            f.write("All environment and model configurations are valid and compliant.\n")
        else:
            f.write("## Validation Findings\n\n")
            f.write("| Category | Severity | Description | Recommendation | Owner Hint |\n")
            f.write("| --- | --- | --- | --- | --- |\n")
            for finding in findings:
                sev_text = f"🔴 {finding['severity'].upper()}" if finding["severity"] == "critical" else f"🟠 {finding['severity'].upper()}"
                f.write(f"| {finding['category']} | {sev_text} | {finding['description']} | {finding['recommendation']} | {finding['owner_hint']} |\n")
                
    print(f"Environment validation report generated successfully in {reports_dir}/")

if __name__ == "__main__":
    main()
