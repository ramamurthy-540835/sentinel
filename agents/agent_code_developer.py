#!/usr/bin/env python3
"""
PRISM Agent 3: Code Developer
Reads estimated architecture and triggers development workflow.
Integrates with Aider for automated code generation.
"""

import sys
import os
import json
import argparse
import subprocess
from pathlib import Path

def log_info(msg):
    print(f"INFO: {msg}")

def log_success(msg):
    print(f"🟢 SUCCESS: {msg}")

def log_error(msg):
    print(f"❌ ERROR: {msg}", file=sys.stderr)

def validate_estimation_exists(prompt_id: str) -> dict:
    """Check if AI estimation exists and is valid."""
    out_dir = Path(f"saved_prompts/{prompt_id}")

    est_path = out_dir / "ai_estimation.md"
    if not est_path.exists():
        log_error(f"Missing AI estimation at {est_path}. Run agent_ai_estimator first.")
        sys.exit(1)

    tokens_path = out_dir / "token_stats.json"
    if not tokens_path.exists():
        log_error(f"Missing token stats at {tokens_path}.")
        sys.exit(1)

    with open(tokens_path, "r") as f:
        tokens = json.load(f)

    # Ensure tokens don't exceed limits (Gemini 3.5 Flash: 1M input, 4M output)
    max_tokens = 4000000
    if tokens.get("total_tokens", 0) > max_tokens:
        log_error(f"Token limit exceeded: {tokens['total_tokens']} > {max_tokens}")
        sys.exit(1)

    return tokens

def run_development_workflow(prompt_id: str, model: str, aider_available: bool = True):
    """Execute code development using estimation."""

    log_info("=" * 60)
    log_info("PRISM CODE DEVELOPER AGENT (Phase 2)")
    log_info("=" * 60)

    out_dir = Path(f"saved_prompts/{prompt_id}")
    est_path = out_dir / "ai_estimation.md"

    with open(est_path, "r") as f:
        estimation = f.read()

    log_info(f"Loaded estimation ({len(estimation)} chars)")

    # Map Vertex AI model names to Aider model keys
    model_mapping = {
        "gemini-3.5-flash": "gemini-flash",
        "xai/grok-4.2-reasoning": "grok-reasoning",
        "xai/grok-4.2-non-reasoning": "grok-fast"
    }
    aider_model = model_mapping.get(model, "gemini-flash")
    log_info(f"Model: {model} → Aider key: {aider_model}")

    if aider_available and os.path.exists("./start_aider.sh"):
        log_info("Aider workflow found. Launching development...")
        try:
            subprocess.run(
                ["bash", "./start_aider.sh", aider_model, str(est_path)],
                check=True
            )
            log_success(f"Code development completed for prompt {prompt_id}!")
        except subprocess.CalledProcessError as e:
            log_error(f"Code development failed: {e.returncode}")
            sys.exit(e.returncode)
    else:
        log_info("No Aider workflow detected. Estimation ready for manual development.")
        log_info(f"Estimation file: {est_path}")
        log_success("Development team can review estimation and proceed manually.")

def main():
    parser = argparse.ArgumentParser(description="PRISM Agent 3: Code Developer")
    parser.add_argument("--prompt-id", required=True, help="Prompt ID context")
    parser.add_argument("--model", default="gemini-3.5-flash", help="Model for development")

    args = parser.parse_args()

    # Validate estimation exists and tokens are within limits
    tokens = validate_estimation_exists(args.prompt_id)
    log_success(f"Estimation validated. Token usage: {tokens['total_tokens']}")

    # Run development
    run_development_workflow(args.prompt_id, args.model)

if __name__ == "__main__":
    main()
