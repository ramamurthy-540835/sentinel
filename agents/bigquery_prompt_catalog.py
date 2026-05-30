#!/usr/bin/env python3
"""
BigQuery Prompt Catalog Agent (Phase 2 SCD Type 2 Edition)

Registers prompt extraction metadata in BigQuery using SCD Type 2 logic:
- Uses LoadJobs (load_table_from_json) to write data directly into the tables,
  completely bypassing the streaming buffer to support DML updates/deletes.
"""

import sys
import json
import argparse
import uuid
from datetime import datetime, timezone
from google.cloud import bigquery
from pathlib import Path


def register_prompt_run(project_id: str, metadata: dict) -> bool:
    """Register/Update prompt version in BigQuery using SCD Type 2 logic and Load Jobs."""
    client = bigquery.Client(project=project_id)
    dataset_id = "prism_prompt_catalog"
    table_id = "prompt_versions"

    prompt_uid = metadata["prompt_uid"]
    run_id = metadata["run_id"]
    version_number = int(metadata["version_number"])
    parent_run_id = metadata.get("parent_run_id") or None
    repeat_mode = metadata["repeat_mode"]
    now_str = datetime.now(timezone.utc).isoformat()

    if repeat_mode == "unchanged_skip":
        print(f"✓ Skip registered: No new version created in SCD Type 2.")
        return True

    # 1. Close the previous active version in BigQuery
    # Since previous rows were added via Load Jobs, DML updates will execute instantly!
    if version_number > 1:
        close_query = f"""
        UPDATE `{project_id}.{dataset_id}.{table_id}`
        SET is_current = FALSE, valid_to = @valid_to
        WHERE prompt_uid = @prompt_uid
          AND is_current = TRUE
          AND run_id != @run_id;
        """
        job_config_close = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("valid_to", "TIMESTAMP", now_str),
                bigquery.ScalarQueryParameter("prompt_uid", "STRING", prompt_uid),
                bigquery.ScalarQueryParameter("run_id", "STRING", run_id),
            ]
        )
        try:
            client.query(close_query, job_config=job_config_close).result()
            print(f"✓ Superseded version {version_number - 1} for prompt {prompt_uid}.")
        except Exception as e:
            print(f"ERROR: Failed to close previous version: {e}")
            return False

    # 2. Insert the new active version using load_table_from_json
    rows_to_insert = [
        {
            "prompt_uid": prompt_uid,
            "source_prompt_id": str(metadata["prompt_id"]),
            "source_system": metadata["source_system"],
            "run_id": run_id,
            "parent_run_id": parent_run_id,
            "version_number": version_number,
            "is_current": True,
            "valid_from": now_str,
            "valid_to": None,
            "raw_hash": metadata["raw_hash"],
            "extracted_hash": metadata["extracted_hash"],
            "status": metadata.get("status", "success"),
            "repeat_mode": repeat_mode,
            "bronze_gcs_uri": metadata["bronze_gcs_uri"],
            "silver_gcs_uri": metadata["silver_gcs_uri"],
            "gold_gcs_uri": metadata["gold_gcs_uri"],
            "chunk_count": metadata["chunk_count"],
            "system_present": metadata["system_present"],
            "user_message_count": metadata["user_message_count"],
            "model_message_count": metadata["model_message_count"],
            "text_attachment_count": metadata["text_attachment_count"],
            "binary_attachment_count": metadata["binary_attachment_count"],
            "raw_size_bytes": metadata["raw_size_bytes"],
            "extracted_chars": metadata["extracted_chars"],
        }
    ]

    try:
        table_ref = f"{project_id}.{dataset_id}.{table_id}"
        table = client.get_table(table_ref)
        job_config = bigquery.LoadJobConfig(
            write_disposition="WRITE_APPEND",
            autodetect=False,
            schema=table.schema,
        )
        # Direct Load Job - Bypasses streaming buffer completely!
        job = client.load_table_from_json(rows_to_insert, table_ref, job_config=job_config)
        job.result()
    except Exception as e:
        print(f"ERROR: Failed to insert new version: {e}")
        return False

    return True


def register_chunks(project_id: str, prompt_uid: str, run_id: str, version_number: int, chunks_dir: Path) -> bool:
    """Register sequential chunks in BigQuery using Load Jobs."""
    client = bigquery.Client(project=project_id)
    dataset_id = "prism_prompt_catalog"
    table_id = "prompt_chunks"

    rows_to_insert = []
    chunk_files = sorted(chunks_dir.glob("chunk_*.md"))

    for chunk_order, chunk_file in enumerate(chunk_files):
        content = chunk_file.read_text()
        char_count = len(content)
        estimated_tokens = max(1, char_count // 4)

        rows_to_insert.append({
            "prompt_uid": prompt_uid,
            "run_id": run_id,
            "version_number": version_number,
            "chunk_id": str(uuid.uuid4()),
            "chunk_order": chunk_order,
            "chunk_file": chunk_file.name,
            "gcs_uri": f"gs://agentproject/saved-prompts/{prompt_uid.split(':')[-1]}/silver/{run_id}/chunks/{chunk_file.name}",
            "char_count": char_count,
            "estimated_tokens": estimated_tokens,
            "role": "system" if "system" in chunk_file.name else "user",
            "artifact_type": "markdown",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

    if not rows_to_insert:
        return True

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
        print(f"ERROR: Failed to insert chunks: {e}")
        return False

    return True


def register_attachments(project_id: str, prompt_uid: str, run_id: str, version_number: int, attachments_dir: Path) -> bool:
    """Register GCS-linked attachments in BigQuery using Load Jobs."""
    client = bigquery.Client(project=project_id)
    dataset_id = "prism_prompt_catalog"
    table_id = "prompt_attachments"

    rows_to_insert = []
    att_files = list(attachments_dir.glob("*.json"))

    for att_file in att_files:
        try:
            att_data = json.loads(att_file.read_text())
        except Exception as e:
            print(f"Warning: Failed to load attachment file {att_file}: {e}")
            continue

        mime_type = att_data.get("mime_type", "unknown")
        if mime_type.startswith("image"):
            att_type = "image"
        elif mime_type.startswith("application/pdf"):
            att_type = "pdf"
        elif mime_type.startswith("text"):
            att_type = "text"
        else:
            att_type = "binary"

        rows_to_insert.append({
            "prompt_uid": prompt_uid,
            "run_id": run_id,
            "version_number": version_number,
            "attachment_id": att_data.get("id") or str(uuid.uuid4()),
            "mime_type": mime_type,
            "attachment_type": att_type,
            "local_path": att_file.name,
            "gcs_uri": f"gs://agentproject/saved-prompts/{prompt_uid.split(':')[-1]}/silver/{run_id}/attachments/{att_file.name}",
            "size_bytes": att_data.get("size_bytes", 0),
            "decoded": att_data.get("decoded", False),
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

    if not rows_to_insert:
        return True

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
        print(f"ERROR: Failed to insert attachments: {e}")
        return False

    return True


def query_latest_runs(project_id: str) -> list:
    """Query latest runs."""
    client = bigquery.Client(project=project_id)
    query = """
    SELECT
      prompt_id,
      run_id,
      raw_hash,
      extracted_hash,
      created_at,
      gcs_run_uri,
      chunk_count,
      user_message_count,
      text_attachment_count,
      binary_attachment_count
    FROM `ctoteam.prism_prompt_catalog.latest_runs`
    ORDER BY created_at DESC
    LIMIT 10;
    """
    try:
        results = client.query(query).result()
        return [dict(row) for row in results]
    except Exception as e:
        print(f"Warning: Failed to query latest runs view: {e}")
        return []


def main():
    parser = argparse.ArgumentParser(description="BigQuery Prompt Catalog Agent")
    parser.add_argument("--prompt-id", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--project-id", default="ctoteam")
    parser.add_argument("--metadata-file", help="JSON file with metadata dict")
    parser.add_argument("--run-folder", help="Path to run folder for chunk/attachment registration")

    args = parser.parse_args()

    metadata = {}
    if args.metadata_file:
        metadata = json.loads(Path(args.metadata_file).read_text())
    else:
        metadata = {
            "prompt_id": args.prompt_id,
            "prompt_uid": f"vertexai:{args.prompt_id}",
            "source_system": "vertexai",
            "run_id": args.run_id,
            "parent_run_id": "",
            "version_number": 1,
            "repeat_mode": "first_run",
            "lifecycle_status": "completed",
            "raw_hash": "unknown",
            "extracted_hash": "unknown",
            "status": "success",
            "bronze_gcs_uri": f"gs://agentproject/saved-prompts/{args.prompt_id}/bronze/{args.run_id}/",
            "silver_gcs_uri": f"gs://agentproject/saved-prompts/{args.prompt_id}/silver/{args.run_id}/",
            "gold_gcs_uri": f"gs://agentproject/saved-prompts/{args.prompt_id}/gold/{args.run_id}/",
            "chunk_count": 0,
            "system_present": False,
            "user_message_count": 0,
            "model_message_count": 0,
            "text_attachment_count": 0,
            "binary_attachment_count": 0,
            "raw_size_bytes": 0,
            "extracted_chars": 0,
        }

    prompt_uid = metadata["prompt_uid"]
    version_number = int(metadata["version_number"])
    run_id = metadata["run_id"]
    repeat_mode = metadata["repeat_mode"]

    print(f"\n[STAGE 1] Registering Prompt Version")
    print(f"{'-'*70}")

    if not register_prompt_run(args.project_id, metadata):
        print("ERROR registering prompt run")
        sys.exit(1)

    print(f"✓ Registered: {prompt_uid} (Version: {version_number}, Mode: {repeat_mode})")

    if repeat_mode != "unchanged_skip" and args.run_folder:
        run_dir = Path(args.run_folder)
        
        chunks_dir = run_dir / "silver" / "chunks"
        if chunks_dir.exists():
            print(f"\n[STAGE 2] Registering Chunks")
            print(f"{'-'*70}")
            if not register_chunks(args.project_id, prompt_uid, run_id, version_number, chunks_dir):
                print("ERROR registering chunks")
                sys.exit(1)
            print(f"✓ Registered {len(list(chunks_dir.glob('*.md')))} chunks")

        att_dir = run_dir / "silver" / "attachments"
        if att_dir.exists():
            print(f"\n[STAGE 3] Registering Attachments")
            print(f"{'-'*70}")
            if not register_attachments(args.project_id, prompt_uid, run_id, version_number, att_dir):
                print("ERROR registering attachments")
                sys.exit(1)
            print(f"✓ Registered {len(list(att_dir.glob('*.json')))} attachments")

    print(f"\n[STAGE 4] Querying Catalog")
    print(f"{'-'*70}")

    latest = query_latest_runs(args.project_id)
    print(f"✓ Latest {len(latest)} extractions in Lakehouse:")
    for row in latest[:5]:
        print(f"  - {row['prompt_id']}: Run {row['run_id'][:8]}... ({row['chunk_count']} chunks, {row['user_message_count']} msgs)")

    print(f"\n{'='*70}")
    print(f"REGISTRATION COMPLETE")
    sys.exit(0)


if __name__ == "__main__":
    main()
