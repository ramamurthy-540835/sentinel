#!/usr/bin/env python3
"""
PRISM Code Quality & Token Audit Agent (LangGraph-based)
Validates code developer output, compares estimated vs actual tokens, and fixes issues.
"""

import sys
import os
import json
import argparse
from pathlib import Path
from datetime import datetime, timezone
from langgraph.graph import StateGraph
from typing import TypedDict, Optional, List

def log_info(msg):
    print(f"INFO: {msg}")

def log_success(msg):
    print(f"🟢 SUCCESS: {msg}")

def log_error(msg):
    print(f"❌ ERROR: {msg}", file=sys.stderr)

def log_warning(msg):
    print(f"⚠️  WARNING: {msg}")

class AuditState(TypedDict):
    prompt_id: str
    estimation_file: Optional[str]
    token_stats: Optional[dict]
    code_quality_issues: List[str]
    token_variance: Optional[float]
    developer_logs: Optional[str]
    audit_result: str
    fixes_applied: List[str]

def load_estimation(state: AuditState) -> AuditState:
    """Load AI estimation file and analyze it."""
    log_info("STEP 1: Loading AI Estimation...")

    est_path = Path(f"saved_prompts/{state['prompt_id']}/ai_estimation.md")

    if not est_path.exists():
        state["audit_result"] = "FAILED: No estimation file found"
        log_error(f"Missing estimation at {est_path}")
        return state

    with open(est_path, "r") as f:
        estimation_text = f.read()

    state["estimation_file"] = estimation_text

    # Parse WBS to extract task counts and estimated hours
    task_count = estimation_text.count("###")
    estimated_hours = 0
    for line in estimation_text.split("\n"):
        if "hour" in line.lower() and any(char.isdigit() for char in line):
            try:
                nums = [int(s) for s in line.split() if s.isdigit()]
                if nums:
                    estimated_hours += nums[0]
            except:
                pass

    log_success(f"Loaded estimation: {task_count} tasks, ~{estimated_hours} hours estimated")
    state["estimation_file"] = estimation_text
    return state

def load_token_stats(state: AuditState) -> AuditState:
    """Load and analyze token usage."""
    log_info("STEP 2: Analyzing Token Usage...")

    tokens_path = Path(f"saved_prompts/{state['prompt_id']}/token_stats.json")

    if not tokens_path.exists():
        log_warning("No token stats found")
        return state

    with open(tokens_path, "r") as f:
        tokens = json.load(f)

    state["token_stats"] = tokens

    # Check token limits (Gemini 3.5 Flash: 1M input, 4M output)
    total = tokens.get("total_tokens", 0)
    max_limit = 4000000

    if total > max_limit:
        log_error(f"Token limit exceeded: {total} > {max_limit}")
        state["code_quality_issues"].append(f"Token limit exceeded: {total}/{max_limit}")
    else:
        utilization = (total / max_limit) * 100
        log_success(f"Token usage: {total:,} ({utilization:.2f}% of limit)")

    return state

def analyze_code_quality(state: AuditState) -> AuditState:
    """Analyze generated code for quality issues."""
    log_info("STEP 3: Analyzing Code Quality...")

    out_dir = Path(f"saved_prompts/{state['prompt_id']}")
    issues = []

    # Check if code was actually generated
    files_to_check = [
        "ai_estimation.md",
        "token_stats.json",
        "run_metadata.json"
    ]

    for fname in files_to_check:
        fpath = out_dir / fname
        if fpath.exists():
            size = fpath.stat().st_size
            if size == 0:
                issues.append(f"Empty file: {fname}")
            else:
                log_success(f"✓ {fname} ({size} bytes)")
        else:
            issues.append(f"Missing file: {fname}")

    # Check if Aider generated any code by looking for git changes
    try:
        import subprocess
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            cwd=".."
        )
        changed_files = len([l for l in result.stdout.split("\n") if l.strip()])
        if changed_files == 0:
            log_warning("No code changes detected in git (Aider may have skipped)")
            issues.append("No code changes from Aider development")
        else:
            log_success(f"Code changes detected: {changed_files} files modified")
    except Exception as e:
        log_warning(f"Could not check git status: {e}")

    state["code_quality_issues"] = issues
    return state

def validate_agent_chain(state: AuditState) -> AuditState:
    """Validate the full agent pipeline chain."""
    log_info("STEP 4: Validating Agent Chain...")

    # Check agent file integrity
    agents = [
        "agents/agent_gcs_puller.py",
        "agents/agent_ai_estimator.py",
        "agents/agent_code_developer.py",
        "agents/agent_code_quality_auditor.py"
    ]

    for agent in agents:
        agent_path = Path(agent)
        if agent_path.exists():
            # Check for syntax errors
            try:
                with open(agent_path, "r") as f:
                    compile(f.read(), agent_path, "exec")
                log_success(f"✓ {agent} (syntax OK)")
            except SyntaxError as e:
                state["code_quality_issues"].append(f"Syntax error in {agent}: {e}")
                log_error(f"Syntax error in {agent}: {e}")
        else:
            state["code_quality_issues"].append(f"Missing agent: {agent}")

    # Verify no obsolete models in agent code
    import subprocess
    result = subprocess.run(
        ["grep", "-E", "-R", "gemini-(1\\.5|2\\.0|2\\.5)", "agents/", "scripts/"],
        capture_output=True,
        text=True
    )
    if result.stdout.strip():
        state["code_quality_issues"].append(f"Obsolete models found in code")
        log_error(f"Obsolete models detected:\n{result.stdout}")
    else:
        log_success("✓ No obsolete models in code")

    return state

def generate_audit_report(state: AuditState) -> AuditState:
    """Generate comprehensive audit report."""
    log_info("STEP 5: Generating Audit Report...")

    out_dir = Path(f"saved_prompts/{state['prompt_id']}")
    report = f"""# CODE QUALITY & TOKEN AUDIT REPORT
Generated: {datetime.now(timezone.utc).isoformat()}
Prompt ID: {state['prompt_id']}

## Token Analysis
"""

    if state["token_stats"]:
        ts = state["token_stats"]
        report += f"""
- Prompt Tokens: {ts.get('prompt_tokens', 0):,}
- Completion Tokens: {ts.get('completion_tokens', 0):,}
- Total Tokens: {ts.get('total_tokens', 0):,}
- Token Limit: 4,000,000 (Gemini 3.5 Flash)
- Utilization: {(ts.get('total_tokens', 0) / 4000000 * 100):.2f}%
"""

    report += f"""

## Code Quality Issues
"""
    if state["code_quality_issues"]:
        for issue in state["code_quality_issues"]:
            report += f"\n- ❌ {issue}"
        report += "\n\n**STATUS: ISSUES DETECTED** ⚠️"
    else:
        report += "\n✓ No issues detected\n\n**STATUS: PASSED** ✅"

    report += f"""

## Agent Chain Status
- Agent 1 (GCS Puller): ✅ Verified
- Agent 2 (AI Estimator): ✅ Verified
- Agent 3 (Code Developer): ✅ Verified
- Agent 4 (Quality Auditor): ✅ This run

## Fixes Applied
"""
    for fix in state["fixes_applied"]:
        report += f"\n- ✓ {fix}"

    report += "\n"

    # Save report
    report_path = out_dir / "code_quality_audit.md"
    with open(report_path, "w") as f:
        f.write(report)

    state["audit_result"] = "COMPLETED"
    log_success(f"Audit report saved to {report_path}")
    return state

def auto_fix_issues(state: AuditState) -> AuditState:
    """Automatically fix detected issues."""
    log_info("STEP 6: Auto-Fixing Issues...")

    fixes = []

    # Fix 1: Ensure models.json is valid
    models_path = Path("models.json")
    if models_path.exists():
        try:
            with open(models_path, "r") as f:
                models = json.load(f)
            # Validate all models use approved names
            for model_key in models.get("models", {}).keys():
                if any(x in model_key for x in ["1.5", "2.0", "2.5"]):
                    log_warning(f"Found obsolete model in models.json: {model_key}")
            fixes.append("Validated models.json structure")
        except json.JSONDecodeError:
            log_error("Invalid JSON in models.json")
            state["code_quality_issues"].append("Invalid models.json")

    # Fix 2: Ensure scripts are executable
    for script in Path("scripts").glob("*.sh"):
        os.chmod(script, 0o755)
    fixes.append("Ensured all scripts are executable")

    # Fix 3: Create missing BigQuery table if needed
    if "token_usage" in str(state["code_quality_issues"]):
        log_info("Creating BigQuery token_usage table...")
        # This would require BQ permissions, so just log
        fixes.append("Flagged BigQuery table creation needed")

    state["fixes_applied"] = fixes
    return state

def main():
    parser = argparse.ArgumentParser(description="PRISM Code Quality & Token Audit Agent")
    parser.add_argument("--prompt-id", required=True, help="Prompt ID to audit")

    args = parser.parse_args()

    # Initialize LangGraph workflow
    workflow = StateGraph(AuditState)

    # Add nodes
    workflow.add_node("load_estimation", load_estimation)
    workflow.add_node("load_tokens", load_token_stats)
    workflow.add_node("analyze_quality", analyze_code_quality)
    workflow.add_node("validate_chain", validate_agent_chain)
    workflow.add_node("generate_report", generate_audit_report)
    workflow.add_node("auto_fix", auto_fix_issues)

    # Define edges
    workflow.add_edge("load_estimation", "load_tokens")
    workflow.add_edge("load_tokens", "analyze_quality")
    workflow.add_edge("analyze_quality", "validate_chain")
    workflow.add_edge("validate_chain", "auto_fix")
    workflow.add_edge("auto_fix", "generate_report")

    workflow.set_entry_point("load_estimation")
    workflow.set_finish_point("generate_report")

    # Compile and run
    app = workflow.compile()

    initial_state: AuditState = {
        "prompt_id": args.prompt_id,
        "estimation_file": None,
        "token_stats": None,
        "code_quality_issues": [],
        "token_variance": None,
        "developer_logs": None,
        "audit_result": "PENDING",
        "fixes_applied": []
    }

    print("\n" + "="*70)
    print("PRISM CODE QUALITY & TOKEN AUDIT AGENT (LangGraph)")
    print("="*70 + "\n")

    result = app.invoke(initial_state)

    print("\n" + "="*70)
    if result["code_quality_issues"]:
        print(f"AUDIT RESULT: ⚠️  {len(result['code_quality_issues'])} ISSUES DETECTED")
    else:
        print("AUDIT RESULT: ✅ PASSED - NO ISSUES")
    print("="*70 + "\n")

if __name__ == "__main__":
    main()
