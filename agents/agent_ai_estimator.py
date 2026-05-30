#!/usr/bin/env python3
"""
PRISM Agent 2: AI Estimator with Gemini 3.5 Flash
Generates architecture specification, WBS, and task estimation.
Logs token usage to BigQuery.
"""

import sys
import os
import json
import argparse
import subprocess
import urllib.request
import urllib.error
import ssl
from datetime import datetime, timezone
from google.cloud import storage, bigquery

def log_info(msg):
    print(f"INFO: {msg}")

def log_success(msg):
    print(f"🟢 SUCCESS: {msg}")

def log_error(msg):
    print(f"❌ ERROR: {msg}", file=sys.stderr)

def get_access_token() -> str:
    """Acquire GCP access token."""
    try:
        res = subprocess.run(
            ["gcloud", "auth", "application-default", "print-access-token"],
            capture_output=True, text=True, check=True
        )
        return res.stdout.strip()
    except Exception:
        log_error("GCP authentication failed.")
        sys.exit(1)

def download_gcs_text_file(bucket_name: str, path: str) -> str:
    """Download text from GCS."""
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(path)
    if not blob.exists():
        return ""
    return blob.download_as_text()

def generate_gemini_estimation(project_id: str, location: str, model_id: str,
                               token: str, system_inst: str, full_assembled: str) -> tuple:
    """Call Vertex AI Gemini 3.5 Flash via global endpoint."""

    url = f"https://aiplatform.googleapis.com/v1/projects/{project_id}/locations/global/publishers/google/models/gemini-3.5-flash:generateContent"

    architect_prompt = f"""You are a Principal Enterprise Software Architect. Analyze the following requirement and provide detailed Software Estimation and Architecture Specification.

SYSTEM INSTRUCTIONS:
{system_inst or "(None)"}

REQUIREMENTS:
{full_assembled}

---
Deliver a markdown report with:
1. COMPLEXITY ANALYSIS & GRADING (1-10 scale)
2. LANGCHAIN & ENTERPRISE ARCHITECTURE FRAMEWORK
3. WORK BREAKDOWN STRUCTURE (WBS) & TASK-HOUR ESTIMATION
4. FILES MODIFICATION MAP (create/modify lists)
"""

    payload = {
        "contents": [{
            "role": "user",
            "parts": [{"text": architect_prompt}]
        }],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 8192,
            "topP": 0.95,
            "topK": 40
        }
    }

    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"))
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("x-goog-user-project", project_id)
    req.add_header("Content-Type", "application/json")

    context = ssl.create_default_context()

    try:
        log_info(f"Invoking Vertex AI Gemini 3.5 Flash for estimation...")
        with urllib.request.urlopen(req, context=context) as response:
            res_body = response.read().decode("utf-8")
            res_json = json.loads(res_body)

            text = res_json["candidates"][0]["content"]["parts"][0]["text"]
            usage = res_json.get("usageMetadata", {})

            return text, {
                "prompt_tokens": usage.get("promptTokenCount", 0),
                "completion_tokens": usage.get("candidatesTokenCount", 0),
                "total_tokens": usage.get("promptTokenCount", 0) + usage.get("candidatesTokenCount", 0)
            }
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8") if e.fp else ""
        log_error(f"Vertex AI API error: {e.code}")
        if err_body:
            print(err_body, file=sys.stderr)
        sys.exit(1)

def log_to_bigquery(project_id: str, prompt_id: str, run_id: str,
                    token_stats: dict, model: str):
    """Log token usage to BigQuery agent_telemetry.token_usage table."""
    try:
        client = bigquery.Client(project=project_id)
        table_id = "ctoteam.agent_telemetry.token_usage"

        row = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "prompt_id": prompt_id,
            "run_id": run_id,
            "agent": "ai_estimator",
            "model": model,
            "prompt_tokens": token_stats["prompt_tokens"],
            "completion_tokens": token_stats["completion_tokens"],
            "total_tokens": token_stats["total_tokens"]
        }

        errors = client.insert_rows_json(table_id, [row])
        if errors:
            log_error(f"BigQuery insert errors: {errors}")
        else:
            log_success(f"Logged tokens to BigQuery: {token_stats['total_tokens']} total")
    except Exception as e:
        log_error(f"Failed to log to BigQuery: {e}")

def main():
    parser = argparse.ArgumentParser(description="PRISM Agent 2: AI Estimator")
    parser.add_argument("--prompt-id", required=True, help="Prompt ID")
    parser.add_argument("--project-id", default="ctoteam")
    parser.add_argument("--location", default="us-central1")
    parser.add_argument("--model", default="gemini-3.5-flash", help="Gemini model")
    parser.add_argument("--bucket", default="agentproject")

    args = parser.parse_args()

    # Load system instructions and requirements
    out_dir = os.path.join("saved_prompts", args.prompt_id)
    sys_path = os.path.join(out_dir, "system_instructions.md")
    asm_path = os.path.join(out_dir, "assembled_requirements.md")
    meta_path = os.path.join(out_dir, "run_metadata.json")

    if not os.path.exists(sys_path) or not os.path.exists(asm_path):
        log_error("Missing system instructions or requirements. Run agent_gcs_puller first.")
        sys.exit(1)

    with open(sys_path, "r") as f:
        system_inst = f.read()
    with open(asm_path, "r") as f:
        full_assembled = f.read()
    with open(meta_path, "r") as f:
        meta = json.load(f)

    run_id = meta.get("run_id")

    # Generate estimation
    token = get_access_token()
    estimation_text, token_stats = generate_gemini_estimation(
        args.project_id, args.location, args.model, token, system_inst, full_assembled
    )

    # Save estimation
    est_path = os.path.join(out_dir, "ai_estimation.md")
    with open(est_path, "w", encoding="utf-8") as f:
        f.write(estimation_text)
    log_success(f"Saved AI Estimation: {est_path}")

    # Log to BigQuery
    log_to_bigquery(args.project_id, args.prompt_id, run_id, token_stats, args.model)

    # Save token stats
    tokens_path = os.path.join(out_dir, "token_stats.json")
    with open(tokens_path, "w", encoding="utf-8") as f:
        json.dump(token_stats, f, indent=2)
    log_success(f"Token stats: {token_stats}")

if __name__ == "__main__":
    main()
