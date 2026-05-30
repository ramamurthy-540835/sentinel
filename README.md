# Prompt-ID Coding Agent

A reusable generic agent that accepts any Vertex AI Studio saved prompt ID, extracts it deterministically, creates a chunked prompt package, and optionally launches Aider for code execution.

## Features

- **Deterministic extraction**: No LLM rewriting of source content
- **Automatic chunking**: Splits large prompts into manageable 15KB chunks
- **Dual interface**: Python script or shell wrapper
- **Aider integration**: Auto-launch with `--run-aider` flag
- **Metadata tracking**: Complete index with extraction stats
- **Multi-format output**: Raw JSON, extracted text, markdown, chunks

## Installation

```bash
cd /home/appadmin/projects/Ram_Projects/DiracDelta/coder
# Ensure venv exists or use system Python
pip install requests
```

## Usage

### Python Interface

```bash
# Extract and prepare
python3 agents/prompt_id_coder_agent.py --prompt-id 3381323161097207808

# Extract and launch Aider
python3 agents/prompt_id_coder_agent.py --prompt-id 7562985783854891008 --run-aider

# Custom settings
python3 agents/prompt_id_coder_agent.py \
  --prompt-id 3381323161097207808 \
  --project-id ctoteam \
  --location us-central1 \
  --chunk-size 20000 \
  --chunk-overlap 2000
```

### Shell Interface

```bash
# Extract only
./scripts/run_prompt_id.sh 3381323161097207808

# Extract and launch Aider
./scripts/run_prompt_id.sh 7562985783854891008 --run-aider
```

## Output Structure

For each prompt ID, creates:

```
saved_prompts/<prompt_id>/
├── raw.json                    # Raw Vertex AI dataset
├── raw_clean.json              # Cleaned, decoded JSON
├── extracted_content.txt       # Full extracted text
├── system.md                   # System instructions (if present)
├── chunk_001.md                # Individual chunk 1
├── chunk_002.md                # Individual chunk 2
├── chunk_N.md                  # ...chunk N
├── master.md                   # Index & usage guide
├── final_assembled.md          # All chunks + master concatenated
└── index.json                  # Metadata & extraction stats
```

## Examples

### Prompt 3381323161097207808 (Small - 4.3 KB)

```bash
python3 agents/prompt_id_coder_agent.py --prompt-id 3381323161097207808
```

**Output:** 1 chunk
- **System Instructions:** Present (PRISM Coder Agent spec)
- **User Prompt:** Requirements for building Prompt-ID Coding Agent
- **Files:** master.md, chunk_001.md, final_assembled.md

### Prompt 7562985783854891008 (Large - 473 KB)

```bash
./scripts/run_prompt_id.sh 7562985783854891008
```

**Output:** 35 chunks
- **System Instructions:** Not present
- **User Prompt:** Comprehensive system design & CLI requirements
- **Files:** master.md, chunk_001.md ... chunk_035.md, final_assembled.md

## How to Use Extracted Prompts with Aider

```bash
# Use master (summary + chunk list)
aider saved_prompts/7562985783854891008/master.md

# Use specific chunk
aider saved_prompts/7562985783854891008/chunk_001.md

# Use full assembled
aider saved_prompts/7562985783854891008/final_assembled.md

# Process multiple chunks
aider saved_prompts/7562985783854891008/chunk_{001..010}.md
```

## Authentication

The agent automatically handles GCP authentication:

1. Tries `gcloud auth print-access-token`
2. Falls back to `gcloud auth application-default print-access-token`
3. If both fail, prints helpful error with auth instructions

```bash
# If auth fails, run:
gcloud auth login --no-launch-browser
gcloud auth application-default login --no-launch-browser
gcloud config set project ctoteam
```

## Implementation Details

### Extraction Pipeline

1. **Fetch**: GET Vertex AI Dataset API with auth token
2. **Clean**: Recursively decode base64 text, strip binary payloads
3. **Extract**: Parse system instructions + user prompt sections
4. **Chunk**: Split text deterministically (no LLM)
5. **Metadata**: Create index.json with stats
6. **Assemble**: Generate master.md + final_assembled.md

### No LLM Rewriting

- Source of truth: Extracted text (100% preserved)
- Chunking: Character-based splitting, not semantic
- Master: Simple markdown guide, not LLM-generated

### Chunking Strategy

- **Size**: 15,000 characters per chunk
- **Overlap**: 1,500 characters between chunks
- **Method**: Deterministic character offset (reproducible)
- **Reason**: Preserve context at chunk boundaries

## File Breakdown

| File | Purpose |
|------|---------|
| `raw.json` | Complete Vertex AI dataset response |
| `raw_clean.json` | JSON with decoded text, stripped binary |
| `extracted_content.txt` | Flat text: system + user sections |
| `system.md` | System instructions only |
| `chunk_*.md` | Individual deterministic chunks |
| `master.md` | Index, metadata, usage guide |
| `final_assembled.md` | master + all chunks concatenated |
| `index.json` | Extraction metadata (chunk count, sizes, timestamp) |

## CLI Arguments

### Python Agent

```
--prompt-id TEXT          Vertex AI saved prompt ID (required)
--project-id TEXT         GCP project (default: ctoteam)
--location TEXT           GCP location (default: us-central1)
--model TEXT              Default LLM model (default: gemini-3.5-flash)
--chunk-size INT          Chunk size in chars (default: 15000)
--chunk-overlap INT       Overlap in chars (default: 1500)
--run-aider               Launch Aider after extraction (flag)
```

### Shell Script

```
./scripts/run_prompt_id.sh <prompt_id> [--run-aider]
```

## Quality Assurance

✅ **No content loss**: 100% fidelity preservation  
✅ **Deterministic**: Reproducible chunking  
✅ **Ordered**: Sequential chunk files (001, 002, ...)  
✅ **Metadata-rich**: Complete extraction stats  
✅ **Aider-ready**: Formats suitable for code generation  

## Troubleshooting

### "ERROR: No GCP token"

```bash
gcloud auth login --no-launch-browser
gcloud config set project ctoteam
```

### "No such file or directory: start_aider.sh"

The agent looks for `./start_aider.sh` in the current directory. If not found:
- Copy from parent directories, or
- Use without `--run-aider` and run Aider manually

### Chunks seem empty or missing

Check `index.json`:
```bash
cat saved_prompts/<prompt_id>/index.json | jq '.chunk_count, .extracted_chars'
```

If `extracted_chars` is 0, the prompt extraction failed. Verify:
- Prompt ID is correct
- GCP credentials are valid
- Dataset exists in Vertex AI

## Design Philosophy

This agent implements the **PRISM Coder Agent** pattern:

1. **Deterministic extraction**: No LLM-based rewriting risks
2. **Chunked storage**: Large prompts stay manageable
3. **Metadata tracking**: Every extraction is auditable
4. **Aider integration**: Seamless code generation workflow
5. **Reusable design**: Works with any prompt ID, no hardcoding

---

**Created:** 2026-05-29  
**Python:** 3.11+  
**Dependencies:** requests, gcloud CLI  
**License:** Internal (ctoteam)
