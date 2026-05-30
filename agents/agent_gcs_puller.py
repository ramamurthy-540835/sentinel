#!/usr/bin/env python3
"""
PRISM Agent 1: GCS Prompt Puller
Fetches latest gold pointer and Silver medallion layers from GCS
"""

import sys
import os
import json
import argparse
import subprocess
from google.cloud import storage

def log_info(msg):
    print(f"INFO: {msg}")

def log_success(msg):
    print(f"🟢 SUCCESS: {msg}")

def log_error(msg):
    print(f"❌ ERROR: {msg}", file=sys.stderr)

def fetch_latest_run_metadata(bucket_name: str, prompt_id: str) -> dict:
    """Fetch gold pointer JSON from GCS."""
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    pointer_blob_path = f"saved-prompts/{prompt_id}/gold/latest.json"

    log_info(f"Downloading gold pointer: gs://{bucket_name}/{pointer_blob_path}")
    blob = bucket.blob(pointer_blob_path)

    if not blob.exists():
        raise FileNotFoundError(f"Latest pointer not found at {pointer_blob_path}")

    metadata_str = blob.download_as_text()
    return json.loads(metadata_str)

def download_gcs_text_file(bucket_name: str, path: str) -> str:
    """Download a text file from GCS, return empty if missing."""
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(path)
    if not blob.exists():
        return ""
    return blob.download_as_text()

def main():
    parser = argparse.ArgumentParser(description="PRISM Agent 1: GCS Prompt Puller")
    parser.add_argument("--prompt-id", required=True, help="Saved Prompt ID")
    parser.add_argument("--bucket", default="agentproject")

    args = parser.parse_args()

    try:
        latest_meta = fetch_latest_run_metadata(args.bucket, args.prompt_id)
        log_success("Retrieved latest gold run pointer.")
    except Exception as e:
        log_error(f"Failed to fetch GCS pointer: {e}")
        sys.exit(1)

    run_id = latest_meta.get("latest_run_id")
    version = latest_meta.get("version_number")

    log_info(f"Retrieving Silver layers for Run ID: {run_id}...")
    silver_base = f"saved-prompts/{args.prompt_id}/silver/{run_id}"

    system_inst = download_gcs_text_file(args.bucket, f"{silver_base}/system.md")
    full_assembled = download_gcs_text_file(args.bucket, f"{silver_base}/final_assembled.md")

    if not full_assembled:
        log_error("Failed to download assembled text from Silver zone.")
        sys.exit(1)

    out_dir = os.path.join("saved_prompts", args.prompt_id)
    os.makedirs(out_dir, exist_ok=True)

    # Save downloaded assets
    sys_path = os.path.join(out_dir, "system_instructions.md")
    with open(sys_path, "w", encoding="utf-8") as f:
        f.write(system_inst)

    asm_path = os.path.join(out_dir, "assembled_requirements.md")
    with open(asm_path, "w", encoding="utf-8") as f:
        f.write(full_assembled)

    # Save metadata
    meta_path = os.path.join(out_dir, "run_metadata.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump({"run_id": run_id, "version": version}, f, indent=2)

    log_success(f"Downloaded system instructions ({len(system_inst)} chars)")
    log_success(f"Downloaded assembled requirements ({len(full_assembled)} chars)")
    log_success(f"Files saved to: {out_dir}/")

if __name__ == "__main__":
    main()
