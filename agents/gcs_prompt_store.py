#!/usr/bin/env python3
"""
GCS Prompt Store Agent (Phase 2 Medallion Edition)

Extracts saved prompts and organizes artifacts inside the prompt ID directory structure in GCS:
- Bronze: gs://agentproject/saved-prompts/<prompt_id>/bronze/<run_id>/
- Silver: gs://agentproject/saved-prompts/<prompt_id>/silver/<run_id>/
- Gold: gs://agentproject/saved-prompts/<prompt_id>/gold/<run_id>/
"""

import sys
import json
import subprocess
import requests
import base64
import argparse
import hashlib
import uuid
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Tuple
from google.cloud import storage, bigquery

def get_auth_token() -> str:
    """Get GCP access token."""
    try:
        return subprocess.check_output(
            ["gcloud", "auth", "print-access-token"], text=True
        ).strip()
    except:
        try:
            return subprocess.check_output(
                ["gcloud", "auth", "application-default", "print-access-token"], text=True
            ).strip()
        except:
            sys.stderr.write("ERROR: gcloud auth failed. Run: gcloud auth login --no-launch-browser\n")
            sys.exit(1)


def compute_md5(data: dict) -> str:
    """Compute MD5 hash of JSON (deterministic)."""
    json_str = json.dumps(data, sort_keys=True, separators=(',', ':'))
    return hashlib.md5(json_str.encode()).hexdigest()


def fetch_prompt(project_id: str, location: str, prompt_id: str, token: str) -> dict:
    """Fetch saved prompt from Vertex AI Dataset API."""
    url = f"https://{location}-aiplatform.googleapis.com/v1/projects/{project_id}/locations/{location}/datasets/{prompt_id}"
    headers = {
        "Authorization": f"Bearer {token}",
        "x-goog-user-project": project_id,
        "Content-Type": "application/json",
    }

    r = requests.get(url, headers=headers, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"Fetch failed {r.status_code}: {r.text}")

    return r.json()


def decode_base64_text(b64_str: str) -> str:
    """Decode base64 text, return original if fails."""
    try:
        return base64.b64decode(b64_str).decode("utf-8", errors="ignore")
    except:
        return f"[Decode failed: {b64_str[:50]}...]"


def clean_node(node: any) -> any:
    """Recursively clean JSON: decode text/plain, strip binary payloads."""
    if isinstance(node, dict):
        has_mime = any(k in node for k in ["mime_type", "mimeType", "mime"])
        if "data" in node and has_mime:
            mime = node.get("mime_type") or node.get("mimeType") or node.get("mime") or ""
            raw_data = node["data"]
            if mime == "text/plain" and raw_data:
                node["data"] = decode_base64_text(raw_data)
            else:
                size = len(raw_data) if raw_data else 0
                node["data"] = f"<stripped_payload:{mime}:{size}_bytes>"

        for k, v in list(node.items()):
            if k == "text" and isinstance(v, str):
                try:
                    nested = json.loads(v)
                    node[k] = json.dumps(clean_node(nested))
                except:
                    pass
            else:
                node[k] = clean_node(v)
    elif isinstance(node, list):
        return [clean_node(item) for item in node]

    return node


def extract_prompt_structure(cleaned_data: dict) -> Tuple[str, List[dict], List[dict]]:
    """
    Extract system instruction, user/model messages, and attachments from cleaned JSON.
    Returns: (system_instruction_text, messages_list, attachments_list)
    """
    system_instruction = ""
    messages = []
    attachments = []

    def parse_prompt_message(msg):
        nonlocal system_instruction

        # Extract system instruction
        sys_inst = msg.get("systemInstruction", {}) or msg.get("system_instruction", {})
        if sys_inst:
            parts = sys_inst.get("parts", [])
            system_instruction = "\n".join([p.get("text", "") for p in parts if "text" in p])

        # Extract user/model messages and attachments
        for content in msg.get("contents", []):
            role = content.get("role", "user")
            if role in ("user", "model", None):
                for part in content.get("parts", []):
                    if "text" in part:
                        messages.append({
                            "role": role or "user",
                            "type": "text",
                            "content": part["text"]
                        })
                    elif "inline_data" in part or "inlineData" in part:
                        data_obj = part.get("inline_data") or part.get("inlineData", {})
                        mime = data_obj.get("mime_type") or data_obj.get("mimeType", "")
                        raw_data = data_obj.get("data", "")

                        attachment_id = str(uuid.uuid4())
                        attachments.append({
                            "id": attachment_id,
                            "mime_type": mime,
                            "role": role or "user",
                            "size_bytes": len(raw_data) if raw_data else 0,
                            "decoded": False
                        })

                        if mime == "text/plain" and raw_data:
                            decoded = decode_base64_text(raw_data)
                            messages.append({
                                "role": role or "user",
                                "type": "attachment",
                                "content": decoded,
                                "attachment_id": attachment_id,
                                "mime_type": mime
                            })

    # Parse metadata.text
    metadata = cleaned_data.get("metadata", {})
    text_str = metadata.get("text", "")
    if text_str:
        try:
            text_json = json.loads(text_str)
            prompt_message = text_json.get("structured_prompt", {}).get("prompt_message", {})
            if prompt_message:
                parse_prompt_message(prompt_message)
        except:
            pass

    # Fallback to promptApiSchema
    if not messages and not system_instruction:
        prompt_api_schema = cleaned_data.get("promptApiSchema", {})
        prompt_message = prompt_api_schema.get("multimodalPrompt", {}).get("promptMessage", {})
        if not prompt_message:
            prompt_message = prompt_api_schema.get("promptMessage", {})
        if prompt_message:
            parse_prompt_message(prompt_message)

    return system_instruction, messages, attachments


def get_previous_version(project_id: str, prompt_uid: str) -> tuple:
    """Queries BigQuery for previous current version metadata."""
    client = bigquery.Client(project=project_id)
    query = """
    SELECT version_number, raw_hash, run_id
    FROM `ctoteam.prism_prompt_catalog.prompt_versions`
    WHERE prompt_uid = @prompt_uid AND is_current = TRUE
    LIMIT 1;
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("prompt_uid", "STRING", prompt_uid)
        ]
    )
    try:
        query_job = client.query(query, job_config=job_config)
        results = list(query_job.result())
        if results:
            row = results[0]
            return row["version_number"], row["raw_hash"], row["run_id"]
    except Exception as e:
        sys.stderr.write(f"Warning: Failed to query previous version: {e}\n")
    return 0, None, None


def insert_event(project_id: str, prompt_uid: str, version_number: int, run_id: str, 
                 event_type: str, lifecycle_status: str, repeat_mode: str, 
                 severity: str, message: str) -> None:
    """Inserts a lifecycle audit event row into BigQuery using load job (bypasses streaming buffer)."""
    client = bigquery.Client(project=project_id)
    dataset_id = "prism_prompt_catalog"
    table_id = "prompt_events"
    
    rows_to_insert = [{
        "event_id": str(uuid.uuid4()),
        "prompt_uid": prompt_uid,
        "version_number": version_number,
        "run_id": run_id,
        "event_type": event_type,
        "lifecycle_status": lifecycle_status,
        "repeat_mode": repeat_mode,
        "severity": severity,
        "message": message,
        "created_at": datetime.now(timezone.utc).isoformat()
    }]
    
    try:
        table_ref = f"{project_id}.{dataset_id}.{table_id}"
        table = client.get_table(table_ref)
        job_config = bigquery.LoadJobConfig(
            write_disposition="WRITE_APPEND",
            autodetect=False,
            schema=table.schema,
        )
        job = client.load_table_from_json(rows_to_insert, table_ref, job_config=job_config)
        job.result()
    except Exception as e:
        sys.stderr.write(f"Warning: Failed to insert event {event_type}: {e}\n")


def create_medallion_folders(prompt_id: str, prompt_uid: str, run_id: str, version_number: int,
                             raw_data: dict, cleaned_data: dict,
                             system_instruction: str, messages: List[dict],
                             attachments: List[dict], raw_hash: str, extracted_hash: str) -> Path:
    """Create local run folder containing bronze, silver, and gold layer structures."""
    base_dir = Path(f"saved_prompts/{prompt_id}/runs/{run_id}")
    base_dir.mkdir(parents=True, exist_ok=True)

    bronze_dir = base_dir / "bronze"
    silver_dir = base_dir / "silver"
    gold_dir = base_dir / "gold"

    bronze_dir.mkdir(exist_ok=True)
    silver_dir.mkdir(exist_ok=True)
    gold_dir.mkdir(exist_ok=True)

    # 1. BRONZE LAYER
    (bronze_dir / "raw.json").write_text(json.dumps(raw_data, indent=2))
    source_metadata = {
        "prompt_id": prompt_id,
        "prompt_uid": prompt_uid,
        "source_system": "vertexai",
        "fetch_time": datetime.now(timezone.utc).isoformat() + "Z",
        "raw_hash": raw_hash
    }
    (bronze_dir / "source_metadata.json").write_text(json.dumps(source_metadata, indent=2))

    # 2. SILVER LAYER
    (silver_dir / "raw_clean.json").write_text(json.dumps(cleaned_data, indent=2))
    if system_instruction:
        (silver_dir / "system.md").write_text(f"# System Instruction\n\n{system_instruction}\n")

    user_msg_dir = silver_dir / "user_messages"
    model_msg_dir = silver_dir / "model_messages"
    user_msg_dir.mkdir(exist_ok=True)
    model_msg_dir.mkdir(exist_ok=True)

    for i, msg in enumerate(messages, 1):
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role == "model":
            (model_msg_dir / f"{i:03d}_{role}.txt").write_text(content)
        else:
            (user_msg_dir / f"{i:03d}_{role}.txt").write_text(content)

    silver_att_dir = silver_dir / "attachments"
    silver_att_dir.mkdir(exist_ok=True)
    for att in attachments:
        (silver_att_dir / f"{att['id']}.json").write_text(json.dumps(att, indent=2))

    # Chunks
    extracted_text = f"=== SYSTEM ===\n{system_instruction}\n\n=== MESSAGES ===\n"
    extracted_text += "\n\n".join([f"[{m.get('role').upper()}] {m.get('content', '')}" for m in messages])

    chunks = []
    chunk_size = 15000
    overlap = 1500
    start = 0
    while start < len(extracted_text):
        end = min(start + chunk_size, len(extracted_text))
        chunks.append(extracted_text[start:end])
        if end >= len(extracted_text):
            break
        start = end - overlap

    silver_chunk_dir = silver_dir / "chunks"
    silver_chunk_dir.mkdir(exist_ok=True)
    chunk_files = []
    for i, chunk in enumerate(chunks, 1):
        chunk_file = f"chunk_{i:03d}.md"
        (silver_chunk_dir / chunk_file).write_text(chunk)
        chunk_files.append(chunk_file)

    master_list = f"# Prompt {prompt_uid}\n\n- **Run ID:** {run_id}\n- **Chunks:** {len(chunks)}\n\n"
    for cf in chunk_files:
        master_list += f"- `{cf}`\n"
    final_assembled = master_list + f"\n{'='*60}\n# CONTENT\n\n" + "\n\n".join(chunks)
    (silver_dir / "final_assembled.md").write_text(final_assembled)

    # 3. GOLD LAYER
    master_content = f"""# SYSTEM INSTRUCTIONS
{system_instruction or "You are an expert enterprise software engineering agent."}

# USER PROMPT TASK AND MESSAGES
{extracted_text}
"""
    (gold_dir / "master.md").write_text(master_content)

    report = {
        "prompt_id": prompt_id,
        "prompt_uid": prompt_uid,
        "run_id": run_id,
        "version_number": version_number,
        "created_at": datetime.now(timezone.utc).isoformat() + "Z",
        "chunk_count": len(chunks),
        "user_message_count": sum(1 for m in messages if m.get("role") != "model"),
        "model_message_count": sum(1 for m in messages if m.get("role") == "model"),
        "text_attachment_count": sum(1 for a in attachments if a["mime_type"].startswith("text")),
        "binary_attachment_count": sum(1 for a in attachments if not a["mime_type"].startswith("text")),
        "raw_size_bytes": len(json.dumps(raw_data)),
        "extracted_chars": len(extracted_text),
        "system_present": bool(system_instruction),
    }
    (gold_dir / "extraction_report.json").write_text(json.dumps(report, indent=2))

    summary = {
        "prompt_uid": prompt_uid,
        "version_number": version_number,
        "chunk_count": len(chunks),
        "user_message_count": len(messages),
        "raw_size_bytes": len(json.dumps(raw_data)),
        "extracted_chars": len(extracted_text)
    }
    (gold_dir / "prompt_summary.json").write_text(json.dumps(summary, indent=2))

    return base_dir


def upload_medallion_to_gcs(run_dir: Path, bucket_name: str, prompt_id: str, run_id: str) -> Tuple[str, str, str]:
    """Uploads the medallion structures nested neatly under the prompt ID in GCS."""
    client = storage.Client()
    bucket = client.bucket(bucket_name)

    layers = ["bronze", "silver", "gold"]
    uris = {}

    for layer in layers:
        local_layer_dir = run_dir / layer
        gcs_prefix = f"saved-prompts/{prompt_id}/{layer}/{run_id}"

        for file_path in local_layer_dir.rglob("*"):
            if file_path.is_file():
                rel_path = file_path.relative_to(local_layer_dir)
                gcs_path = f"{gcs_prefix}/{rel_path}".replace("\\", "/")
                blob = bucket.blob(gcs_path)
                blob.upload_from_filename(file_path)
        
        uris[layer] = f"gs://{bucket_name}/{gcs_prefix}/"

    return uris["bronze"], uris["silver"], uris["gold"]


def update_latest_pointer_in_gold(bucket_name: str, prompt_id: str, run_id: str, version_number: int, silver_uri: str) -> str:
    """Updates latest pointer in GCS nested inside the gold hierarchy."""
    client = storage.Client()
    bucket = client.bucket(bucket_name)

    latest_data = {
        "prompt_id": prompt_id,
        "latest_run_id": run_id,
        "version_number": version_number,
        "updated_at": datetime.now(timezone.utc).isoformat() + "Z",
        "gcs_uri": silver_uri
    }

    pointer_path = f"saved-prompts/{prompt_id}/gold/{run_id}/latest_pointer.json"
    blob = bucket.blob(pointer_path)
    blob.upload_from_string(json.dumps(latest_data, indent=2), content_type="application/json")

    # Sync latest.json at prompt root folder as well
    root_blob = bucket.blob(f"saved-prompts/{prompt_id}/gold/latest.json")
    root_blob.upload_from_string(json.dumps(latest_data, indent=2), content_type="application/json")

    return f"gs://{bucket_name}/{pointer_path}"


def main():
    parser = argparse.ArgumentParser(description="GCS Prompt Store Agent (Phase 2)")
    parser.add_argument("--prompt-id", required=True)
    parser.add_argument("--project-id", default="ctoteam")
    parser.add_argument("--location", default="us-central1")
    parser.add_argument("--bucket", default="agentproject")
    parser.add_argument("--force", action="store_true")

    args = parser.parse_args()

    prompt_uid = f"vertexai:{args.prompt_id}"

    sys.stderr.write(f"\n{'='*70}\n")
    sys.stderr.write(f"GCS PROMPT STORE AGENT (PHASE 2)\n")
    sys.stderr.write(f"{'='*70}\n")
    sys.stderr.write(f"Prompt ID: {args.prompt_id}\n")
    sys.stderr.write(f"Prompt UID: {prompt_uid}\n")
    sys.stderr.write(f"Project: {args.project_id}\n")
    sys.stderr.write(f"GCS Bucket: gs://{args.bucket}/saved-prompts/{args.prompt_id}/\n")

    token = get_auth_token()

    # STAGE 1: Fetch
    sys.stderr.write(f"\n[STAGE 1] Fetching Prompt\n")
    sys.stderr.write(f"{'-'*70}\n")
    raw_data = fetch_prompt(args.project_id, args.location, args.prompt_id, token)
    raw_hash = compute_md5(raw_data)
    sys.stderr.write(f"✓ Fetched (hash: {raw_hash[:8]}...)\n")

    prev_version, prev_raw_hash, prev_run_id = get_previous_version(args.project_id, prompt_uid)

    if prev_raw_hash == raw_hash and not args.force:
        repeat_mode = "unchanged_skip"
        lifecycle_status = "skipped_unchanged"
        sys.stderr.write(f"✓ Change Detection: Hash matches previous version {prev_version}. Skipping extraction.\n")
        
        insert_event(
            project_id=args.project_id,
            prompt_uid=prompt_uid,
            version_number=prev_version,
            run_id=prev_run_id or "00000000-0000-0000-0000-000000000000",
            event_type="skipped_unchanged",
            lifecycle_status=lifecycle_status,
            repeat_mode=repeat_mode,
            severity="info",
            message=f"Hash matches previous version {prev_version}. Extraction skipped."
        )

        metadata = {
            "prompt_id": args.prompt_id,
            "prompt_uid": prompt_uid,
            "source_system": "vertexai",
            "run_id": prev_run_id or "00000000-0000-0000-0000-000000000000",
            "parent_run_id": "",
            "version_number": prev_version,
            "repeat_mode": repeat_mode,
            "lifecycle_status": lifecycle_status,
            "raw_hash": raw_hash,
            "extracted_hash": "",
            "status": "success",
            "bronze_gcs_uri": f"gs://{args.bucket}/saved-prompts/{args.prompt_id}/bronze/{prev_run_id}/" if prev_run_id else "",
            "silver_gcs_uri": f"gs://{args.bucket}/saved-prompts/{args.prompt_id}/silver/{prev_run_id}/" if prev_run_id else "",
            "gold_gcs_uri": f"gs://{args.bucket}/saved-prompts/{args.prompt_id}/gold/{prev_run_id}/" if prev_run_id else "",
            "chunk_count": 0,
            "system_present": False,
            "user_message_count": 0,
            "model_message_count": 0,
            "text_attachment_count": 0,
            "binary_attachment_count": 0,
            "raw_size_bytes": len(json.dumps(raw_data)),
            "extracted_chars": 0
        }
        print(json.dumps(metadata, indent=2))
        return

    if prev_version == 0:
        repeat_mode = "first_run"
        version_number = 1
        parent_run_id = None
        sys.stderr.write(f"✓ Change Detection: First extraction run initialized.\n")
    elif args.force:
        repeat_mode = "force_new_version"
        version_number = prev_version + 1
        parent_run_id = prev_run_id
        sys.stderr.write(f"✓ Change Detection: Force flag active. Upgrading version to {version_number}.\n")
    else:
        repeat_mode = "changed_new_version"
        version_number = prev_version + 1
        parent_run_id = prev_run_id
        sys.stderr.write(f"✓ Change Detection: Change detected. Upgrading version to {version_number}.\n")

    run_id = str(uuid.uuid4())

    insert_event(
        project_id=args.project_id,
        prompt_uid=prompt_uid,
        version_number=version_number,
        run_id=run_id,
        event_type="created",
        lifecycle_status="created",
        repeat_mode=repeat_mode,
        severity="info",
        message="Extraction execution initialized."
    )

    insert_event(
        project_id=args.project_id,
        prompt_uid=prompt_uid,
        version_number=version_number,
        run_id=run_id,
        event_type="extracting",
        lifecycle_status="extracting",
        repeat_mode=repeat_mode,
        severity="info",
        message="Extracting system instructions, messages, and attachments."
    )

    # STAGE 2: Clean & Extract
    sys.stderr.write(f"\n[STAGE 2] Extracting Content\n")
    sys.stderr.write(f"{'-'*70}\n")
    cleaned_data = clean_node(raw_data)
    system_instruction, messages, attachments = extract_prompt_structure(cleaned_data)
    extracted_text_payload = system_instruction + "".join(m.get("content", "") for m in messages)
    extracted_hash = hashlib.md5(extracted_text_payload.encode()).hexdigest()
    sys.stderr.write(f"✓ System: {bool(system_instruction)} | Messages: {len(messages)} | Attachments: {len(attachments)}\n")
    sys.stderr.write(f"✓ Extracted hash: {extracted_hash[:8]}...\n")

    # STAGE 3: Create local run folder
    sys.stderr.write(f"\n[STAGE 3] Creating Medallion Directories Locally\n")
    sys.stderr.write(f"{'-'*70}\n")
    run_dir = create_medallion_folders(
        args.prompt_id, prompt_uid, run_id, version_number,
        raw_data, cleaned_data, system_instruction, messages, attachments,
        raw_hash, extracted_hash
    )
    sys.stderr.write(f"✓ Run ID: {run_id}\n")
    sys.stderr.write(f"✓ Local folder: {run_dir}\n")

    insert_event(
        project_id=args.project_id,
        prompt_uid=prompt_uid,
        version_number=version_number,
        run_id=run_id,
        event_type="bronze_completed",
        lifecycle_status="bronze_completed",
        repeat_mode=repeat_mode,
        severity="info",
        message="Raw bronze dataset and source metadata stored."
    )

    # STAGE 4: Upload to GCS
    sys.stderr.write(f"\n[STAGE 4] Uploading Medallion Layers to GCS\n")
    sys.stderr.write(f"{'-'*70}\n")
    bronze_uri, silver_uri, gold_uri = upload_medallion_to_gcs(run_dir, args.bucket, args.prompt_id, run_id)
    sys.stderr.write(f"✓ Uploaded Bronze: {bronze_uri}\n")
    sys.stderr.write(f"✓ Uploaded Silver: {silver_uri}\n")
    
    insert_event(
        project_id=args.project_id,
        prompt_uid=prompt_uid,
        version_number=version_number,
        run_id=run_id,
        event_type="silver_completed",
        lifecycle_status="silver_completed",
        repeat_mode=repeat_mode,
        severity="info",
        message="Structured silver messages, chunks, and decoded assets uploaded."
    )

    # STAGE 5: Update pointer in Gold
    sys.stderr.write(f"\n[STAGE 5] Registering Gold Pointer and Metadata\n")
    sys.stderr.write(f"{'-'*70}\n")
    latest_pointer_uri = update_latest_pointer_in_gold(args.bucket, args.prompt_id, run_id, version_number, silver_uri)
    sys.stderr.write(f"✓ Uploaded Gold: {gold_uri}\n")
    sys.stderr.write(f"✓ Latest Pointer: {latest_pointer_uri}\n")

    insert_event(
        project_id=args.project_id,
        prompt_uid=prompt_uid,
        version_number=version_number,
        run_id=run_id,
        event_type="gold_completed",
        lifecycle_status="gold_completed",
        repeat_mode=repeat_mode,
        severity="info",
        message="Gold analytical indexes and latest pointers updated."
    )

    insert_event(
        project_id=args.project_id,
        prompt_uid=prompt_uid,
        version_number=version_number,
        run_id=run_id,
        event_type="completed",
        lifecycle_status="completed",
        repeat_mode=repeat_mode,
        severity="info",
        message="Prompt extraction lifecycle finished successfully."
    )

    chunk_count = len(list((run_dir / "silver" / "chunks").glob("chunk_*.md")))
    extracted_chars = len(system_instruction) + sum(len(m.get("content", "")) for m in messages)

    metadata = {
        "prompt_id": args.prompt_id,
        "prompt_uid": prompt_uid,
        "source_system": "vertexai",
        "run_id": run_id,
        "parent_run_id": parent_run_id or "",
        "version_number": version_number,
        "repeat_mode": repeat_mode,
        "lifecycle_status": "completed",
        "raw_hash": raw_hash,
        "extracted_hash": extracted_hash,
        "status": "success",
        "bronze_gcs_uri": bronze_uri,
        "silver_gcs_uri": silver_uri,
        "gold_gcs_uri": gold_uri,
        "chunk_count": chunk_count,
        "system_present": bool(system_instruction),
        "user_message_count": sum(1 for m in messages if m.get("role") != "model"),
        "model_message_count": sum(1 for m in messages if m.get("role") == "model"),
        "text_attachment_count": sum(1 for a in attachments if a["mime_type"].startswith("text")),
        "binary_attachment_count": sum(1 for a in attachments if not a["mime_type"].startswith("text")),
        "raw_size_bytes": len(json.dumps(raw_data)),
        "extracted_chars": extracted_chars
    }

    sys.stderr.write(f"\n{'='*70}\n")
    sys.stderr.write(f"EXTRACTION & UPLOAD COMPLETE\n")
    sys.stderr.write(f"{'='*70}\n")
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
