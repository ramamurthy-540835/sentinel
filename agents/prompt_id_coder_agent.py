#!/usr/bin/env python3
"""
PRISM Prompt-ID Coding Agent

Fetches saved prompts from Google Cloud Vertex AI Dataset API,
extracts and decodes contents deterministically, builds a local prompt package,
and optionally triggers Aider to perform the coding task.
"""

import os
import sys
import argparse
import json
import base64
import subprocess
import urllib.request
import urllib.error
import ssl
import uuid
from datetime import datetime, timezone
from typing import Tuple, List


def log_info(msg: str) -> None:
    print(f"INFO: {msg}")


def log_success(msg: str) -> None:
    print(f"SUCCESS: {msg}")


def log_warning(msg: str) -> None:
    print(f"WARNING: {msg}")


def log_error(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)


def get_gcloud_config(key: str) -> str | None:
    """Retrieve an active gcloud configuration value."""
    try:
        res = subprocess.run(
            ["gcloud", "config", "get-value", key],
            capture_output=True,
            text=True,
            check=True,
        )
        val = res.stdout.strip()
        if val and "(unset)" not in val:
            return val
    except Exception:
        pass
    return None


def get_access_token() -> str:
    """Retrieve active Google Cloud credentials token."""
    try:
        res = subprocess.run(
            ["gcloud", "auth", "print-access-token"],
            capture_output=True,
            text=True,
            check=True,
        )
        token = res.stdout.strip()
        if token:
            log_success("Acquired active gcloud session access token.")
            return token
    except Exception:
        pass

    try:
        res = subprocess.run(
            ["gcloud", "auth", "application-default", "print-access-token"],
            capture_output=True,
            text=True,
            check=True,
        )
        token = res.stdout.strip()
        if token:
            log_success("Acquired Application Default Credentials access token.")
            return token
    except Exception:
        pass

    log_error("Failed to acquire access token. Authentication is required.")
    print("\nPlease log in to GCP using:")
    print("  gcloud auth login --no-launch-browser")
    print("  gcloud auth application-default login --no-launch-browser")
    print("  gcloud config set project ctoteam\n")
    sys.exit(1)


def fetch_prompt_dataset(project: str, location: str, prompt_id: str, token: str) -> dict:
    """Fetch raw prompt dataset JSON from Vertex AI Dataset API."""
    url = (
        f"https://{location}-aiplatform.googleapis.com/v1/"
        f"projects/{project}/locations/{location}/datasets/{prompt_id}"
    )
    log_info(f"Fetching dataset resource: {url}")

    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/json")

    context = ssl.create_default_context()

    try:
        with urllib.request.urlopen(req, context=context) as response:
            body = response.read().decode("utf-8")
            return json.loads(body)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8") if e.fp else ""
        log_error(f"HTTP Error {e.code}: {e.reason}")
        if body:
            try:
                err_json = json.loads(body)
                print(json.dumps(err_json, indent=2), file=sys.stderr)
            except Exception:
                print(body, file=sys.stderr)
        raise RuntimeError(f"GCP API returned HTTP {e.code}") from e
    except Exception as e:
        raise RuntimeError(f"Failed to connect to GCP API: {e}") from e


def decode_base64_text(b64_str: str) -> str:
    """Decode base64 string to UTF-8 text."""
    try:
        return base64.b64decode(b64_str).decode("utf-8", errors="ignore")
    except Exception as e:
        return f"[Failed to decode base64 attachment text: {e}]"


def clean_node(node):
    """Recursively clean JSON: decode text/plain base64, strip binary payloads."""
    if isinstance(node, dict):
        has_mime = "mime_type" in node or "mimeType" in node or "mime" in node
        if "data" in node and has_mime:
            mime = node.get("mime_type") or node.get("mimeType") or node.get("mime") or ""
            raw_data = node["data"]
            if mime == "text/plain" and raw_data:
                node["data"] = decode_base64_text(raw_data)
            else:
                size = len(raw_data) if raw_data else 0
                node["data"] = f"[Binary Attachment: {mime}, size: {size} bytes]"

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


def extract_prompt_data(cleaned_data: dict) -> Tuple[str, str, List[dict]]:
    """Deterministic prompt extraction from cleaned Vertex JSON."""
    system_instruction = ""
    user_parts: List[str] = []
    attachments: List[dict] = []

    def parse_prompt_message(msg):
        nonlocal system_instruction
        sys_inst = msg.get("systemInstruction", {}) or msg.get("system_instruction", {})
        if sys_inst:
            parts = sys_inst.get("parts", [])
            system_instruction = "\n".join([p.get("text", "") for p in parts if "text" in p])

        contents = msg.get("contents", [])
        for content in contents:
            role = content.get("role", "user")
            if role in ("user", "model") or not role:
                for part in content.get("parts", []):
                    if "text" in part:
                        user_parts.append(f"[{(role or 'user').upper()}] {part["text"]}")
                    elif "inline_data" in part or "inlineData" in part:
                        data_obj = part.get("inline_data", {}) or part.get("inlineData", {})
                        mime = data_obj.get("mime_type", "") or data_obj.get("mimeType", "")
                        raw_data = data_obj.get("data", "")

                        if mime == "text/plain" and raw_data:
                            user_parts.append(f"[{(role or 'user').upper()}][ATTACHMENT:text/plain] {raw_data}")
                            attachments.append(
                                {"type": mime, "size_bytes": len(raw_data), "status": "decoded"}
                            )
                        else:
                            size = len(raw_data) if raw_data else 0
                            user_parts.append(f"[{(role or 'user').upper()}][BINARY_ATTACHMENT] {mime} ({size} bytes)")
                            attachments.append(
                                {"type": mime, "size_bytes": size, "status": "stripped"}
                            )

    metadata = cleaned_data.get("metadata", {})
    text_str = metadata.get("text", "")
    if text_str:
        try:
            text_json = json.loads(text_str)
            prompt_message = text_json.get("structured_prompt", {}).get("prompt_message", {})
            if prompt_message:
                parse_prompt_message(prompt_message)
        except Exception:
            pass

    if not user_parts and not system_instruction:
        prompt_api_schema = cleaned_data.get("promptApiSchema", {})
        prompt_message = prompt_api_schema.get("multimodalPrompt", {}).get("promptMessage", {})
        if not prompt_message:
            prompt_message = prompt_api_schema.get("promptMessage", {})
        if prompt_message:
            parse_prompt_message(prompt_message)

    raw_user_prompt = "\n\n".join(user_parts)
    return system_instruction.strip(), raw_user_prompt.strip(), attachments


def create_local_prompt_package(
    prompt_id: str,
    raw_json: dict,
    cleaned_json: dict,
    system_instruction: str,
    user_content: str,
    attachments: List[dict],
) -> str:
    """Prepare directory layout and save standardized prompt artifacts."""
    prompt_root = os.path.join("saved_prompts", prompt_id)
    runs_root = os.path.join(prompt_root, "runs")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + str(uuid.uuid4())[:8]
    out_dir = os.path.join(runs_root, run_id)
    os.makedirs(out_dir, exist_ok=True)

    with open(os.path.join(out_dir, "raw.json"), "w", encoding="utf-8") as f:
        json.dump(raw_json, f, indent=2)

    with open(os.path.join(out_dir, "raw_clean.json"), "w", encoding="utf-8") as f:
        json.dump(cleaned_json, f, indent=2)

    with open(os.path.join(out_dir, "system.md"), "w", encoding="utf-8") as f:
        f.write(system_instruction)

    extracted_full = (
        f"=== SYSTEM INSTRUCTIONS ===\n{system_instruction or '(None)'}\n\n"
        f"=== USER PROMPT ===\n{user_content or '(None)'}\n"
    )
    with open(os.path.join(out_dir, "extracted_content.txt"), "w", encoding="utf-8") as f:
        f.write(extracted_full)

    # Deterministic chunking for large prompts
    chunk_size = 15000
    overlap = 1500
    chunk_dir = out_dir
    chunks = []
    start = 0
    while start < len(user_content):
        end = min(start + chunk_size, len(user_content))
        chunks.append(user_content[start:end])
        if end >= len(user_content):
            break
        start = end - overlap

    for idx, chunk in enumerate(chunks, 1):
        with open(os.path.join(chunk_dir, f"chunk_{idx:03d}.md"), "w", encoding="utf-8") as f:
            f.write(chunk)

    assembled_content = (
        f"# System Instruction\n\n{system_instruction}\n\n"
        f"--------------------------------------------------\n\n"
        f"# User Prompt\n\n{user_content}"
    )
    with open(os.path.join(out_dir, "final_assembled.md"), "w", encoding="utf-8") as f:
        f.write(assembled_content)

    master_content = f"""# SYSTEM INSTRUCTIONS
{system_instruction or "You are an expert enterprise software engineering agent."}

# USER PROMPT TASK
{user_content}
"""
    master_path = os.path.join(out_dir, "master.md")
    with open(master_path, "w", encoding="utf-8") as f:
        f.write(master_content)

    index_data = {
        "prompt_id": prompt_id,
        "raw_size_bytes": len(json.dumps(raw_json)),
        "extracted_chars": len(extracted_full),
        "system_instruction_present": bool(system_instruction),
        "attachments_summary": attachments,
        "chunk_count": len(chunks),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    with open(os.path.join(out_dir, "index.json"), "w", encoding="utf-8") as f:
        json.dump(index_data, f, indent=2)

    latest = {
        "prompt_id": prompt_id,
        "run_id": run_id,
        "run_path": out_dir,
        "master_path": master_path,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "system_instruction_length": len(system_instruction),
        "user_content_length": len(user_content),
        "chunk_count": len(chunks),
    }
    os.makedirs(prompt_root, exist_ok=True)
    with open(os.path.join(prompt_root, "latest_run.json"), "w", encoding="utf-8") as f:
        json.dump(latest, f, indent=2)

    log_success(f"Assembled prompt package at {master_path}")
    return master_path


def run_aider_process(prompt_id: str) -> None:
    """Launch start_aider.sh wrapper on the latest extracted package."""
    latest_path = os.path.join("saved_prompts", prompt_id, "latest_run.json")
    if not os.path.exists(latest_path):
        log_error(f"Cannot run Aider: latest_run.json does not exist at {latest_path}")
        sys.exit(1)
    latest = json.load(open(latest_path, "r", encoding="utf-8"))
    master_path = latest.get("master_path", "")
    if not master_path or not os.path.exists(master_path):
        log_error(f"Cannot run Aider: master.md does not exist at {master_path}")
        sys.exit(1)

    aider_script = "./start_aider.sh"
    if not os.path.exists(aider_script):
        log_error("Could not locate start_aider.sh script in current path.")
        sys.exit(1)

    log_info(f"Executing: {aider_script} gemini-flash {master_path}")
    try:
        subprocess.run([aider_script, "gemini-flash", master_path], check=True)
        log_success("Aider coding workflow completed successfully.")
    except subprocess.CalledProcessError as e:
        log_error(f"start_aider.sh failed with exit code {e.returncode}")
        sys.exit(e.returncode)
    except Exception as e:
        log_error(f"Unexpected error executing Aider script: {e}")
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="PRISM Prompt-ID Coding Agent")
    parser.add_argument("--prompt-id", required=True, help="Saved Prompt ID from Vertex AI Dataset")
    parser.add_argument("--project", help="GCP Project ID")
    parser.add_argument("--location", help="GCP Location")
    parser.add_argument("--run-aider", action="store_true", help="Launch start_aider.sh")
    parser.add_argument("--dry-run", action="store_true", help="Perform extraction and packaging but skip running Aider")

    args = parser.parse_args()

    project = args.project or get_gcloud_config("project") or "ctoteam"
    location = args.location or "us-central1"
    prompt_id = args.prompt_id

    log_info(f"Configuration: Project={project}, Location={location}, PromptID={prompt_id}")

    token = get_access_token()

    try:
        raw_json = fetch_prompt_dataset(project, location, prompt_id, token)
        log_success("Fetched raw prompt dataset.")
    except Exception as e:
        log_error(f"Failed to fetch prompt: {e}")
        sys.exit(1)

    try:
        cleaned_json = clean_node(raw_json)
        system_instruction, user_content, attachments = extract_prompt_data(cleaned_json)
        log_info(f"System instruction length: {len(system_instruction)} chars")
        log_info(f"User content length: {len(user_content)} chars")
    except Exception as e:
        log_error(f"Failed to parse and clean prompt JSON layout: {e}")
        sys.exit(1)

    try:
        create_local_prompt_package(
            prompt_id=prompt_id,
            raw_json=raw_json,
            cleaned_json=cleaned_json,
            system_instruction=system_instruction,
            user_content=user_content,
            attachments=attachments,
        )
    except Exception as e:
        log_error(f"Failed to save local prompt package files: {e}")
        sys.exit(1)

    if args.dry_run:
        log_success("Dry-run execution completed. Artifacts verified.")
    elif args.run_aider:
        run_aider_process(prompt_id)


if __name__ == "__main__":
    main()
