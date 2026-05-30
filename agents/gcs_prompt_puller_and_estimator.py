#!/usr/bin/env python3
"""
PRISM GCS Prompt Puller and AI Estimator Agent

Flow:
1. Resolves latest metadata pointer from gs://agentproject/saved-prompts/<prompt_id>/gold/latest.json
2. Pulls system instructions and full assembled text from GCS Silver layer.
3. Invokes Vertex AI Gemini API (Gemini 3.5 Flash) to generate a detailed Work Breakdown Structure,
   LangChain implementation blueprint, and project estimation.
4. Generates a structured Claude-Optimized Prompt package saved locally.
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
from google.cloud import storage

# Console Logging
def log_info(msg):
    print(f"INFO: {msg}")

def log_success(msg):
    print(f"🟢 SUCCESS: {msg}")

def log_error(msg):
    print(f"❌ ERROR: {msg}", file=sys.stderr)


def get_access_token() -> str:
    """Acquire GCP access token safely using gcloud or ADC."""
    try:
        res = subprocess.run(
            ["gcloud", "auth", "print-access-token"],
            capture_output=True, text=True, check=True
        )
        return res.stdout.strip()
    except Exception:
        try:
            res = subprocess.run(
                ["gcloud", "auth", "application-default", "print-access-token"],
                capture_output=True, text=True, check=True
            )
            return res.stdout.strip()
        except Exception:
            log_error("GCP authentication failed. Please run 'gcloud auth application-default login'")
            sys.exit(1)


def fetch_latest_run_metadata(bucket_name: str, prompt_id: str) -> dict:
    """Fetch gold pointer JSON from GCS."""
    client = storage.Client()
    bucket = client.bucket(bucket_name)

    pointer_blob_path = f"saved-prompts/{prompt_id}/gold/latest.json"
    log_info(f"Downloading gold pointer: gs://{bucket_name}/{pointer_blob_path}")

    blob = bucket.blob(pointer_blob_path)
    if not blob.exists():
        raise FileNotFoundError(f"Latest pointer not found at gs://{bucket_name}/{pointer_blob_path}")

    metadata_str = blob.download_as_text()
    return json.loads(metadata_str)


def download_gcs_text_file(bucket_name: str, path: str) -> str:
    """Helper to safely download a text file from GCS, returning empty if missing."""
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(path)
    if not blob.exists():
        return ""
    return blob.download_as_text()


def generate_gemini_estimation(project_id: str, location: str, model_id: str, token: str,
                               prompt_id: str, system_inst: str, full_assembled: str) -> str:
    """Call Vertex AI Gemini API using raw REST to avoid SDK conflicts."""
    if location == "global":
        url = f"https://aiplatform.googleapis.com/v1/projects/{project_id}/locations/global/publishers/google/models/{model_id}:generateContent"
    else:
        url = f"https://{location}-aiplatform.googleapis.com/v1/projects/{project_id}/locations/{location}/publishers/google/models/{model_id}:generateContent"

    # Construct a highly structured, analytical prompt for the Architect model
    architect_prompt = f"""You are a Principal Enterprise Software Architect. Analyze the following extracted prompt requirement and provide a highly detailed, professional Software Estimation and Architecture Specification.

PROMPT SYSTEM INSTRUCTIONS:
{system_inst or "(None)"}

PROMPT ASSEMBLED REQUIREMENT & CHUNKS:
{full_assembled}

----------------------------------------------------------------------
Deliver a complete markdown report containing the following mandatory sections:

1. **EXECUTIVE COMPLEXITY ANALYSIS & GRADING**
   - Complexity Score (1-10 scale)
   - Architectural Constraints (e.g., streaming buffers, multi-layered zones, concurrency)
   - Scope boundaries (What is in-scope vs out-of-scope for Phase 1/Phase 2)

2. **LANGCHAIN & ENTERPRISE ARCHITECTURE FRAMEWORK**
   - Specific LangChain modules to use (e.g., LangGraph, Custom Tools, ChatModels)
   - Agent State and Memory architecture
   - Class-diagram relationship maps

3. **WORK BREAKDOWN STRUCTURE (WBS) & TASK-HOUR ESTIMATION**
   - Tabular task list with individual estimated hours
   - Total estimated effort (in developer-hours)
   - Critical path risk analysis (e.g., Vertex endpoints, GCS IO, concurrency)

4. **FILES MODIFICATION MAP**
   - Precise list of files to create with directories
   - Precise list of existing files to modify
"""

    payload = {
        "contents": [{
            "role": "user",
            "parts": [{"text": architect_prompt}]
        }],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 8192
        }
    }

    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"))
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/json")

    context = ssl.create_default_context()

    try:
        log_info(f"Invoking Vertex AI Gemini model ({model_id}) for architecture estimation...")
        with urllib.request.urlopen(req, context=context) as response:
            res_body = response.read().decode("utf-8")
            res_json = json.loads(res_body)
            # Safely extract generated text
            return res_json["candidates"][0]["content"]["parts"][0]["text"]
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8") if e.fp else ""
        log_error(f"Vertex AI API error: {e.code} - {e.reason}")
        if err_body:
            print(err_body, file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        log_error(f"Failed to communicate with Vertex AI API: {e}")
        sys.exit(1)


def generate_claude_prompt(prompt_id: str, run_id: str, version: int,
                           system_inst: str, full_assembled: str, estimation: str) -> str:
    """Generate a highly cohesive markdown prompt copy-pasteable into Claude."""
    return f"""# CLAUDE MASTER IMPLEMENTATION CONTEXT

This prompt context contains the exact requirements, system-extracted instructions, and architectural estimations for the project under Prompt ID `{prompt_id}` (Run ID: {run_id}, Version {version}).

---

## 🛠️ ARCHITECTURE & TASK ESTIMATION (Vertex AI Gemini specification)

{estimation}

---

## 🏛️ SYSTEM INSTRUCTION RULESET

Use the following exact system specifications to govern code generation:

```text
{system_inst or "No specific system rules defined."}
```

---

## 📝 REQUIREMENT SPECS / FULL TEMPLATE CONTEXT

{full_assembled}

---

## 🚀 CLAUDE DIRECTIVE

Implement this project following the above Architecture Specification. Ensure all modules are clean, modular, tested, and PEP8 compliant.
"""


def main():
    parser = argparse.ArgumentParser(description="PRISM GCS Prompt Puller & Estimator")
    parser.add_argument("--prompt-id", required=True, help="Saved Prompt ID to pull from GCS")
    parser.add_argument("--project-id", default="ctoteam")
    parser.add_argument("--location", default="us-central1")
    parser.add_argument("--bucket", default="agentproject")
    parser.add_argument("--model", default="gemini-3.5-flash", help="Vertex AI model identifier")

    args = parser.parse_args()

    # 1. Fetch pointer
    try:
        latest_meta = fetch_latest_run_metadata(args.bucket, args.prompt_id)
        log_success("Retrieved latest gold run pointer.")
    except Exception as e:
        log_error(f"Failed to fetch GCS pointer metadata: {e}")
        sys.exit(1)

    run_id = latest_meta.get("latest_run_id", "unknown")
    version = latest_meta.get("version_number", 1)

    # 2. Pull Silver Layers
    log_info(f"Retrieving Silver Medallion layers for Run ID: {run_id}...")
    silver_base = f"saved-prompts/{args.prompt_id}/silver/{run_id}"

    system_inst = download_gcs_text_file(args.bucket, f"{silver_base}/system.md")
    full_assembled = download_gcs_text_file(args.bucket, f"{silver_base}/final_assembled.md")

    if not full_assembled:
        log_error("Failed to download any assembled text from the Silver zone in GCS.")
        sys.exit(1)

    log_success(f"Downloaded system instruction ({len(system_inst)} chars) and assembled requirements ({len(full_assembled)} chars).")

    # 3. Call Gemini to get AI Estimation
    token = get_access_token()
    estimation_text = generate_gemini_estimation(
        args.project_id, args.location, args.model, token,
        args.prompt_id, system_inst, full_assembled
    )

    # 4. Generate local structured packages
    out_dir = os.path.join("saved_prompts", args.prompt_id)
    os.makedirs(out_dir, exist_ok=True)

    # Save estimation
    est_path = os.path.join(out_dir, "ai_estimation.md")
    with open(est_path, "w", encoding="utf-8") as f:
        f.write(estimation_text)
    log_success(f"Saved AI Estimation Report: {est_path}")

    # Save Claude Prompt
    claude_prompt = generate_claude_prompt(
        args.prompt_id, run_id, version, system_inst, full_assembled, estimation_text
    )
    claude_path = os.path.join(out_dir, "claude_prompt.md")
    with open(claude_path, "w", encoding="utf-8") as f:
        f.write(claude_prompt)
    log_success(f"Saved Claude-Optimized Copy-Pasteable Prompt: {claude_path}")


if __name__ == "__main__":
    main()
