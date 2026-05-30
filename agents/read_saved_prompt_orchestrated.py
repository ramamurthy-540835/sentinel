import sys
import json
import subprocess
import requests
import base64
from pathlib import Path
from typing import TypedDict

# Load configuration
try:
    cfg = json.load(open("configs/saved_prompt_config.json"))
except FileNotFoundError:
    print("Config file configs/saved_prompt_config.json not found.")
    exit(1)

project = cfg["project_id"]
location = cfg["location"]
prompt_id = cfg["prompt_id"]
planner_model = cfg.get("planner_model", "gemini-3.5-flash")
generator_model = cfg.get("generator_model", "gemini-3.5-flash")

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
        print("\nERROR: gcloud token retrieval failed.")
        print("Please run: gcloud auth application-default login")
        exit(1)

headers = {
    "Authorization": "Bearer " + token,
    "x-goog-user-project": project,
    "Content-Type": "application/json",
}

# ============================================================================
# STAGE 0: DETERMINISTIC EXTRACTION (Same as before - Source of Truth)
# ============================================================================
print("\n[STAGE 0] Deterministic Extraction - Source of Truth")
print("=" * 70)

url = "https://" + location + "-aiplatform.googleapis.com/v1/projects/" + project + "/locations/" + location + "/datasets/" + prompt_id

print(f"Fetching dataset {prompt_id}...")
r = requests.get(url, headers=headers, timeout=30)

if r.status_code != 200:
    print(f"ERROR: Dataset fetch failed with status {r.status_code}")
    print(f"Details: {r.text}")
    exit(1)

data = r.json()
Path("saved_prompts").mkdir(exist_ok=True)
Path("saved_prompts/raw_" + prompt_id + ".json").write_text(json.dumps(data, indent=2))
print(f"✓ Raw metadata saved: saved_prompts/raw_{prompt_id}.json")

# Helper function to decode base64 text
def decode_base64_text(b64_str):
    try:
        decoded_bytes = base64.b64decode(b64_str)
        return decoded_bytes.decode("utf-8", errors="ignore")
    except Exception as e:
        return "[Failed to decode text: " + str(e) + "]"

# Clean recursive nodes
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
Path("saved_prompts/raw_clean_" + prompt_id + ".json").write_text(json.dumps(cleaned_data, indent=2))
print(f"✓ Cleaned metadata saved: saved_prompts/raw_clean_{prompt_id}.json")

# Extract system instructions and user parts
extracted_system_instruction = ""
extracted_user_parts = []

def parse_prompt_message(msg):
    global extracted_system_instruction
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

if not extracted_user_parts and not extracted_system_instruction:
    prompt_api_schema = cleaned_data.get("promptApiSchema", {})
    prompt_message = prompt_api_schema.get("multimodalPrompt", {}).get("promptMessage", {})
    if not prompt_message:
        prompt_message = prompt_api_schema.get("promptMessage", {})
    if prompt_message:
        parse_prompt_message(prompt_message)

raw_user_prompt = "\n\n".join(extracted_user_parts)

# LangChain chunking
print("\nApplying LangChain RecursiveCharacterTextSplitter...")
try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
except ImportError:
    print("Installing langchain-text-splitters...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "langchain-text-splitters", "-q"])
    from langchain_text_splitters import RecursiveCharacterTextSplitter

text_splitter = RecursiveCharacterTextSplitter(chunk_size=15000, chunk_overlap=1500, length_function=len)
chunks = text_splitter.split_text(raw_user_prompt)
print(f"✓ Prompt chunked into {len(chunks)} segments")

optimized_user_prompt = "\n\n---\n\n".join(chunks)

extracted_text_content = (
    "=== SYSTEM INSTRUCTIONS ===\n"
    + (extracted_system_instruction if extracted_system_instruction else "(None)")
    + "\n\n=== USER PROMPT ===\n"
    + (optimized_user_prompt if optimized_user_prompt else "(None)")
    + "\n"
)
Path("saved_prompts/extracted_content.txt").write_text(extracted_text_content, encoding="utf-8")
print(f"✓ Extracted content saved: {len(extracted_text_content)} bytes")

# ============================================================================
# STAGE 1: PLANNER LLM - Analyze structure and create blueprint
# ============================================================================
print("\n[STAGE 1] Planner LLM - Structural Analysis")
print("=" * 70)

planner_system_prompt = (
    "You are an expert prompt analyst. Analyze the given extracted prompt and create a structured blueprint. "
    "Identify: (1) main objectives, (2) key constraints/rules, (3) technical context, (4) required outputs, "
    "(5) critical sections that must be preserved. Output a JSON object with these keys: "
    '{"objectives": [...], "constraints": [...], "technical_context": {...}, "critical_sections": [...]}. '
    "Your analysis guides the Generator LLM to create the final markdown with perfect fidelity."
)

planner_payload = {
    "contents": [
        {
            "role": "user",
            "parts": [
                {
                    "text": f"Analyze this extracted prompt and create a structured blueprint:\n\n{extracted_text_content}"
                }
            ]
        }
    ],
    "systemInstruction": {
        "parts": [{"text": planner_system_prompt}]
    },
    "generationConfig": {
        "temperature": 0.3,
        "maxOutputTokens": 4096
    }
}

planner_url = (
    f"https://aiplatform.googleapis.com/v1/projects/{project}/locations/global"
    f"/publishers/google/models/{planner_model}:generateContent"
)

print(f"Invoking {planner_model} for structural analysis...")
planner_response = requests.post(planner_url, headers=headers, json=planner_payload, timeout=60)

if planner_response.status_code != 200:
    print(f"ERROR: Planner LLM failed with status {planner_response.status_code}")
    exit(1)

planner_data = planner_response.json()
planner_output = ""
for candidate in planner_data.get("candidates", []):
    for part in candidate.get("content", {}).get("parts", []):
        if "text" in part:
            planner_output = part["text"]
            break

print(f"✓ Planner analysis complete ({len(planner_output)} chars)")

# Clean up markdown code fences from planner output
planner_clean = planner_output
if planner_clean.startswith("```json"):
    planner_clean = planner_clean[7:]
elif planner_clean.startswith("```"):
    planner_clean = planner_clean[3:]
if planner_clean.endswith("```"):
    planner_clean = planner_clean[:-3]
planner_clean = planner_clean.strip()

# Try to parse as JSON, fallback to raw text
try:
    planner_json = json.loads(planner_clean)
    planner_blueprint = json.dumps(planner_json, indent=2)
except json.JSONDecodeError:
    planner_blueprint = planner_clean

Path("saved_prompts/planner_blueprint.json").write_text(planner_blueprint, encoding="utf-8")
print(f"✓ Planner blueprint saved: saved_prompts/planner_blueprint.json")

# ============================================================================
# STAGE 2: GENERATOR LLM - Process chunks in parallel and assemble
# ============================================================================
print("\n[STAGE 2] Generator LLM - Parallel Chunk Processing")
print("=" * 70)

import concurrent.futures

generator_system_prompt = (
    "You are a markdown formatter. Format the given prompt chunk into clean markdown. "
    "Preserve ALL content exactly as given. Add markdown structure (headers, lists) only where natural. "
    "Output ONLY the formatted markdown for this chunk, no code fences or meta-commentary."
)

def process_chunk(idx, chunk_text):
    """Process a single chunk through the Generator LLM."""
    generator_payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": f"Format this prompt chunk into clean markdown:\n\n{chunk_text}"
                    }
                ]
            }
        ],
        "systemInstruction": {
            "parts": [{"text": generator_system_prompt}]
        },
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 2048
        }
    }

    generator_url = (
        f"https://aiplatform.googleapis.com/v1/projects/{project}/locations/global"
        f"/publishers/google/models/{generator_model}:generateContent"
    )

    try:
        response = requests.post(generator_url, headers=headers, json=generator_payload, timeout=60)

        if response.status_code == 200:
            data = response.json()
            for candidate in data.get("candidates", []):
                for part in candidate.get("content", {}).get("parts", []):
                    if "text" in part:
                        result = part["text"]
                        # Clean fences
                        if result.startswith("```"):
                            result = result.split("```", 2)[1] if "```" in result[3:] else result[3:]
                        return (idx, result.strip())

        return (idx, chunk_text)  # Fallback to original if generation fails
    except Exception as e:
        print(f"  ⚠ Chunk {idx} generation failed: {e}")
        return (idx, chunk_text)

# Process chunks in parallel
print(f"Processing {len(chunks)} chunks in parallel...")
chunk_results = {}

with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
    futures = {executor.submit(process_chunk, i, chunk): i for i, chunk in enumerate(chunks)}

    for future in concurrent.futures.as_completed(futures):
        try:
            idx, result = future.result()
            chunk_results[idx] = result
            print(f"  ✓ Chunk {idx} complete ({len(result)} chars)")
        except Exception as e:
            idx = futures[future]
            chunk_results[idx] = chunks[idx]
            print(f"  ✗ Chunk {idx} failed: {e}")

# Assemble chunks in order
generated_markdown = "\n\n---\n\n".join([chunk_results[i] for i in range(len(chunks))])

# Add header structure using planner blueprint
header_text = "# Assembled Prompt\n\n"
header_text += "## Blueprint\n\n"
header_text += planner_blueprint + "\n\n"
header_text += "---\n\n"

generated_markdown = header_text + generated_markdown

print(f"✓ Markdown generated ({len(generated_markdown)} chars)")

# ============================================================================
# OUTPUT: Save orchestrated result
# ============================================================================
print("\n[OUTPUT] Persisting Results")
print("=" * 70)

Path("saved_prompts/assembled_prompt_orchestrated.md").write_text(generated_markdown, encoding="utf-8")
Path("saved_prompts/" + prompt_id + "_orchestrated.md").write_text(generated_markdown, encoding="utf-8")

print(f"✓ Orchestrated prompt saved: saved_prompts/assembled_prompt_orchestrated.md")
print(f"✓ Orchestrated prompt saved: saved_prompts/{prompt_id}_orchestrated.md")

# Also save a summary of the orchestration process
orchestration_summary = {
    "prompt_id": prompt_id,
    "project_id": project,
    "location": location,
    "stages": {
        "stage_0": {
            "name": "Deterministic Extraction",
            "input": "Raw Vertex AI Dataset",
            "output": "extracted_content.txt",
            "status": "complete"
        },
        "stage_1": {
            "name": "Planner LLM Analysis",
            "model": planner_model,
            "output": "planner_blueprint.json",
            "status": "complete"
        },
        "stage_2": {
            "name": "Generator LLM Markdown",
            "model": generator_model,
            "output": "assembled_prompt_orchestrated.md",
            "status": "complete"
        }
    },
    "output_size_bytes": len(generated_markdown),
    "timestamp": str(Path("saved_prompts/assembled_prompt_orchestrated.md").stat().st_mtime)
}

Path("saved_prompts/orchestration_summary.json").write_text(json.dumps(orchestration_summary, indent=2))
print(f"✓ Orchestration summary saved: saved_prompts/orchestration_summary.json")

print("\n" + "=" * 70)
print("ORCHESTRATION COMPLETE")
print("=" * 70)
print(f"\n--- ORCHESTRATED PROMPT PREVIEW ---\n{generated_markdown[:1500]}\n...\n")
