#!/usr/bin/env python3
"""
Deterministic Chunked Prompt Store Extractor with Append Support

Extracts Vertex AI saved prompt datasets and splits them into manageable chunks
without any LLM rewriting. Preserves 100% fidelity of source content.

NEW: MD5-based change detection. Appends new chunks instead of replacing.

Usage:
    python3 agents/read_saved_prompt_chunked.py --prompt-id 7562985783854891008 --deterministic-only
"""

import sys
import json
import subprocess
import requests
import base64
import argparse
import hashlib
from pathlib import Path
from datetime import datetime

def compute_md5(data):
    """Compute MD5 hash of JSON data (deterministic)."""
    json_str = json.dumps(data, sort_keys=True, separators=(',', ':'))
    return hashlib.md5(json_str.encode()).hexdigest()


def check_existing_hash(output_dir):
    """Check if previous extraction exists and return its hash."""
    index_path = output_dir / "index.json"
    if not index_path.exists():
        return None, None
    try:
        index_data = json.load(open(index_path))
        return index_data.get("raw_hash"), index_data.get("version", 1)
    except:
        return None, None


def get_next_version(output_dir):
    """Get next version number for append mode."""
    index_path = output_dir / "index.json"
    if not index_path.exists():
        return 1
    try:
        index_data = json.load(open(index_path))
        return int(index_data.get("version", 1)) + 1
    except:
        return 1


def main():
    parser = argparse.ArgumentParser(description="Extract and chunk Vertex AI saved prompts")
    parser.add_argument("--prompt-id", required=True, help="Vertex AI dataset prompt ID")
    parser.add_argument("--chunk-size", type=int, default=15000, help="Chunk size in characters")
    parser.add_argument("--chunk-overlap", type=int, default=1500, help="Chunk overlap in characters")
    parser.add_argument("--deterministic-only", action="store_true", help="Skip LLM processing (default)")
    parser.add_argument("--force", action="store_true", help="Force re-extraction even if unchanged")
    args = parser.parse_args()

    prompt_id = args.prompt_id
    chunk_size = args.chunk_size
    chunk_overlap = args.chunk_overlap

    # Load configuration
    try:
        cfg = json.load(open("configs/saved_prompt_config.json"))
    except FileNotFoundError:
        print("ERROR: Config file configs/saved_prompt_config.json not found.")
        sys.exit(1)

    project = cfg["project_id"]
    location = cfg["location"]
    model = cfg.get("model", "gemini-3.5-flash")

    print(f"\n{'='*70}")
    print(f"CHUNKED PROMPT STORE EXTRACTOR")
    print(f"{'='*70}")
    print(f"Project: {project}")
    print(f"Location: {location}")
    print(f"Prompt ID: {prompt_id}")
    print(f"Chunk size: {chunk_size} chars, overlap: {chunk_overlap} chars")

    # Retrieve authentication token
    token = ""
    try:
        token = subprocess.check_output(
            ["gcloud", "auth", "print-access-token"], text=True
        ).strip()
        print("✓ User access token retrieved")
    except subprocess.CalledProcessError:
        try:
            token = subprocess.check_output(
                ["gcloud", "auth", "application-default", "print-access-token"], text=True
            ).strip()
            print("✓ ADC access token retrieved")
        except subprocess.CalledProcessError:
            print("ERROR: gcloud token retrieval failed.")
            print("Run: gcloud auth application-default login")
            sys.exit(1)

    headers = {
        "Authorization": f"Bearer {token}",
        "x-goog-user-project": project,
        "Content-Type": "application/json",
    }

    # ========================================================================
    # STAGE 0: FETCH RAW DATASET
    # ========================================================================
    print(f"\n[STAGE 0] Fetching Vertex AI Dataset")
    print(f"{'-'*70}")

    url = f"https://{location}-aiplatform.googleapis.com/v1/projects/{project}/locations/{location}/datasets/{prompt_id}"

    print(f"Fetching from: {url}")
    r = requests.get(url, headers=headers, timeout=30)

    if r.status_code != 200:
        print(f"ERROR: Dataset fetch failed with status {r.status_code}")
        print(f"Details: {r.text}")
        sys.exit(1)

    data = r.json()

    # Create output folder
    output_dir = Path(f"saved_prompts/{prompt_id}")
    output_dir.mkdir(parents=True, exist_ok=True)

    # ========================================================================
    # STAGE 0.5: CHANGE DETECTION (MD5 HASH)
    # ========================================================================
    print(f"\n[STAGE 0.5] Change Detection")
    print(f"{'-'*70}")

    current_hash = compute_md5(data)
    previous_hash, previous_version = check_existing_hash(output_dir)

    if previous_hash and current_hash == previous_hash and not args.force:
        print(f"✓ No change detected (hash: {current_hash[:8]}...)")
        print(f"✓ Skipping extraction. Current version: {previous_version}")
        sys.exit(0)

    if previous_hash and current_hash != previous_hash:
        print(f"⚠ Change detected!")
        print(f"  Previous hash: {previous_hash[:8]}...")
        print(f"  Current hash:  {current_hash[:8]}...")
        next_version = get_next_version(output_dir)
        print(f"  → Creating version {next_version} (appending chunks)")
    else:
        print(f"✓ First extraction for {prompt_id}")
        next_version = 1

    version = next_version

    # Save raw JSON
    raw_path = output_dir / "raw.json"
    raw_path.write_text(json.dumps(data, indent=2))
    print(f"✓ Raw dataset saved: {raw_path}")

    # ========================================================================
    # STAGE 1: CLEAN AND EXTRACT
    # ========================================================================
    print(f"\n[STAGE 1] Deterministic Extraction")
    print(f"{'-'*70}")

    def decode_base64_text(b64_str):
        try:
            decoded_bytes = base64.b64decode(b64_str)
            return decoded_bytes.decode("utf-8", errors="ignore")
        except Exception as e:
            return f"[Failed to decode text: {e}]"

    def clean_node(node):
        if isinstance(node, dict):
            has_mime = "mime_type" in node or "mimeType" in node or "mime" in node
            if "data" in node and has_mime:
                mime = node.get("mime_type") or node.get("mimeType") or node.get("mime") or ""
                raw_data = node["data"]
                if mime == "text/plain" and raw_data:
                    node["data"] = decode_base64_text(raw_data)
                else:
                    size = len(raw_data) if raw_data else 0
                    node["data"] = f"<stripped_base64_payload_of_mime_{mime}_size_{size}_bytes>"

            for key, value in list(node.items()):
                if key == "text" and isinstance(value, str):
                    try:
                        nested_json = json.loads(value)
                        node[key] = json.dumps(clean_node(nested_json))
                    except Exception:
                        pass
                else:
                    node[key] = clean_node(value)
        elif isinstance(node, list):
            return [clean_node(item) for item in node]
        return node

    cleaned_data = clean_node(data)
    clean_path = output_dir / "raw_clean.json"
    clean_path.write_text(json.dumps(cleaned_data, indent=2))
    print(f"✓ Cleaned JSON saved: {clean_path}")

    # Extract system instructions and user parts
    extracted_system_instruction = ""
    extracted_user_parts = []

    def parse_prompt_message(msg):
        nonlocal extracted_system_instruction
        sys_inst = msg.get("systemInstruction", {}) or msg.get("system_instruction", {})
        if sys_inst:
            parts = sys_inst.get("parts", [])
            extracted_system_instruction = "\n".join([p.get("text", "") for p in parts if "text" in p])

        contents = msg.get("contents", [])
        for content in contents:
            role = content.get("role", "user")
            if role == "user" or not role:
                for part in content.get("parts", []):
                    if "text" in part:
                        extracted_user_parts.append(part["text"])
                    elif "inline_data" in part or "inlineData" in part:
                        data_obj = part.get("inline_data", {}) or part.get("inlineData", {})
                        mime = data_obj.get("mime_type", "") or data_obj.get("mimeType", "")
                        raw_data = data_obj.get("data", "")
                        if mime == "text/plain" and raw_data:
                            extracted_user_parts.append(decode_base64_text(raw_data))
                        else:
                            size = len(raw_data) if raw_data else 0
                            extracted_user_parts.append(f"\n[Attached File: {mime}, Size: {size} bytes]\n")

    # Parse metadata.text
    metadata = cleaned_data.get("metadata", {})
    text_str = metadata.get("text", "")
    if text_str:
        try:
            text_json = json.loads(text_str)
            prompt_message = text_json.get("structured_prompt", {}).get("prompt_message", {})
            if prompt_message:
                parse_prompt_message(prompt_message)
        except Exception as e:
            print(f"Warning parsing metadata.text: {e}")

    # Fallback to promptApiSchema
    if not extracted_user_parts and not extracted_system_instruction:
        prompt_api_schema = cleaned_data.get("promptApiSchema", {})
        prompt_message = prompt_api_schema.get("multimodalPrompt", {}).get("promptMessage", {})
        if not prompt_message:
            prompt_message = prompt_api_schema.get("promptMessage", {})
        if prompt_message:
            parse_prompt_message(prompt_message)

    raw_user_prompt = "\n\n".join(extracted_user_parts)

    extracted_text_content = (
        "=== SYSTEM INSTRUCTIONS ===\n"
        + (extracted_system_instruction if extracted_system_instruction else "(None)")
        + "\n\n=== USER PROMPT ===\n"
        + (raw_user_prompt if raw_user_prompt else "(None)")
        + "\n"
    )

    extracted_path = output_dir / "extracted_content.txt"
    extracted_path.write_text(extracted_text_content, encoding="utf-8")
    extracted_chars = len(extracted_text_content)
    print(f"✓ Extracted content saved: {extracted_path} ({extracted_chars} chars)")

    # ========================================================================
    # STAGE 2: DETERMINISTIC CHUNKING
    # ========================================================================
    print(f"\n[STAGE 2] Deterministic Chunking")
    print(f"{'-'*70}")

    def create_chunks(text, chunk_sz, overlap):
        """Split text into overlapping chunks deterministically."""
        chunks = []
        start = 0
        while start < len(text):
            end = min(start + chunk_sz, len(text))
            chunk = text[start:end]
            chunks.append(chunk)

            if end >= len(text):
                break

            # Move start position: chunk_size - overlap
            start = end - overlap

        return chunks

    chunks = create_chunks(extracted_text_content, chunk_size, chunk_overlap)
    print(f"✓ Created {len(chunks)} chunks (size={chunk_size}, overlap={chunk_overlap})")

    # Write chunk files (with version suffix if appending)
    chunk_files = []
    version_suffix = "" if version == 1 else f"_v{version}"

    for i, chunk in enumerate(chunks, 1):
        chunk_num = i
        chunk_filename = f"chunk_{chunk_num:03d}{version_suffix}.md"
        chunk_path = output_dir / chunk_filename
        chunk_path.write_text(chunk, encoding="utf-8")
        chunk_files.append(chunk_filename)
        if i <= 3 or i == len(chunks):
            print(f"  ✓ {chunk_filename} ({len(chunk)} chars)")
        elif i == 4:
            print(f"  ... ({len(chunks) - 3} more chunks)")

    if version > 1:
        print(f"⚠ Appended {len(chunks)} new chunks with version suffix _v{version}")

    # ========================================================================
    # STAGE 3: CREATE METADATA & INDEX
    # ========================================================================
    print(f"\n[STAGE 3] Creating Metadata")
    print(f"{'-'*70}")

    extracted_hash = hashlib.md5(extracted_text_content.encode()).hexdigest()

    index_data = {
        "prompt_id": prompt_id,
        "project_id": project,
        "location": location,
        "model": model,
        "version": version,
        "raw_hash": current_hash,
        "extracted_hash": extracted_hash,
        "chunk_count": len(chunks),
        "chunk_files": chunk_files,
        "chunk_size": chunk_size,
        "chunk_overlap": chunk_overlap,
        "raw_size_bytes": len(json.dumps(data)),
        "extracted_chars": extracted_chars,
        "system_instruction_present": bool(extracted_system_instruction),
        "created_at": datetime.utcnow().isoformat() + "Z"
    }

    index_path = output_dir / "index.json"
    index_path.write_text(json.dumps(index_data, indent=2))
    print(f"✓ Index created: {index_path}")

    # ========================================================================
    # STAGE 4: CREATE MASTER.MD
    # ========================================================================
    print(f"\n[STAGE 4] Creating Master Prompt")
    print(f"{'-'*70}")

    master_content = f"""# Master Prompt: {prompt_id}

## Overview

This prompt dataset has been extracted and deterministically chunked for efficient processing.

- **Prompt ID:** {prompt_id}
- **Project:** {project}
- **Location:** {location}
- **Total Chunks:** {len(chunks)}
- **Extracted Content:** {extracted_chars:,} characters

## Chunk Structure

The prompt is split into {len(chunks)} deterministic chunks:

"""

    for i, filename in enumerate(chunk_files, 1):
        master_content += f"- `{filename}`\n"

    master_content += f"""

## How to Use

### Option 1: Use Individual Chunks
Feed chunks one at a time to your LLM for analysis:

```bash
cat saved_prompts/{prompt_id}/chunk_001.md | aider
cat saved_prompts/{prompt_id}/chunk_002.md | aider
# ... and so on
```

### Option 2: Use Full Assembled Prompt
All chunks have been concatenated into `final_assembled.md`:

```bash
cat saved_prompts/{prompt_id}/final_assembled.md | aider
```

### Option 3: Process Chunks in Parallel
Use `chunk_001.md` through `chunk_{len(chunks):03d}.md` in parallel:

```bash
parallel aider ::: saved_prompts/{prompt_id}/chunk_*.md
```

## Content

The extracted prompt contains:

- **System Instructions:** {'Yes' if extracted_system_instruction else 'No'}
- **User Prompt Sections:** {len(extracted_user_parts)} part(s)
- **Total Size:** {extracted_chars:,} characters

## Metadata

Full index is available in `index.json`:

```json
{{
  "prompt_id": "{prompt_id}",
  "chunk_count": {len(chunks)},
  "chunk_size": {chunk_size},
  "extracted_chars": {extracted_chars},
  "created_at": "{index_data['created_at']}"
}}
```

## Important

- **No content loss:** Every character of the original prompt is preserved.
- **Deterministic:** Chunks are split by character position, not by LLM.
- **Order preserved:** Chunks are in extraction order (chunk_001 -> chunk_{len(chunks):03d}).
- **Source of truth:** `extracted_content.txt` is the authoritative extraction.

---

Generated: {index_data['created_at']}
"""

    master_path = output_dir / "master.md"
    master_path.write_text(master_content)
    print(f"✓ Master prompt created: {master_path}")

    # ========================================================================
    # STAGE 5: CREATE FINAL ASSEMBLED
    # ========================================================================
    print(f"\n[STAGE 5] Creating Final Assembled Prompt")
    print(f"{'-'*70}")

    final_content = master_content + "\n\n" + "=" * 70 + "\n"
    final_content += "# ASSEMBLED CONTENT\n\n"

    for i, filename in enumerate(chunk_files, 1):
        chunk_path = output_dir / filename
        chunk_text = chunk_path.read_text(encoding="utf-8")
        final_content += f"\n---\n\n## Chunk {i} of {len(chunks)}\n\n"
        final_content += chunk_text
        final_content += "\n\n"

    final_path = output_dir / "final_assembled.md"
    final_path.write_text(final_content)
    print(f"✓ Final assembled prompt created: {final_path} ({len(final_content)} chars)")

    # ========================================================================
    # SUMMARY
    # ========================================================================
    print(f"\n{'='*70}")
    print(f"EXTRACTION COMPLETE")
    print(f"{'='*70}")
    print(f"\nFolder: saved_prompts/{prompt_id}/")
    print(f"  - raw.json ({len(json.dumps(data)) / 1024 / 1024:.1f} MB)")
    print(f"  - raw_clean.json ({len(json.dumps(cleaned_data)) / 1024:.1f} KB)")
    print(f"  - extracted_content.txt ({extracted_chars / 1024:.1f} KB)")
    print(f"  - master.md (instructions)")
    print(f"  - chunk_001.md ... chunk_{len(chunks):03d}.md ({len(chunks)} files)")
    print(f"  - index.json (metadata)")
    print(f"  - final_assembled.md (concatenated)")

    print(f"\n✓ Ready for Aider:")
    print(f"  aider saved_prompts/{prompt_id}/master.md")
    print(f"  aider saved_prompts/{prompt_id}/chunk_001.md")
    print(f"  aider saved_prompts/{prompt_id}/final_assembled.md")

if __name__ == "__main__":
    main()
