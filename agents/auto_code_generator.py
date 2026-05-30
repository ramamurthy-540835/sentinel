#!/usr/bin/env python3
"""
Automated Code Generator - No Human In Loop

Reads extracted prompt and generates code automatically using Gemini.
Saves generated files without requiring user interaction.
"""

import sys, json, subprocess, requests, argparse
from pathlib import Path

def get_auth_token():
    try:
        return subprocess.check_output(["gcloud", "auth", "print-access-token"], text=True).strip()
    except:
        print("ERROR: No GCP token. Run: gcloud auth login --no-launch-browser")
        sys.exit(1)

def read_prompt(prompt_file):
    """Read the extracted prompt."""
    try:
        return Path(prompt_file).read_text()
    except FileNotFoundError:
        print(f"ERROR: Prompt file not found: {prompt_file}")
        sys.exit(1)

def generate_code(prompt_text, project_id="ctoteam", model="gemini-3.5-flash"):
    """Call Gemini to generate code automatically."""
    print(f"\n[GENERATE] Calling {model} to generate code...")
    
    token = get_auth_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "x-goog-user-project": project_id,
        "Content-Type": "application/json",
    }
    
    payload = {
        "contents": [{
            "role": "user",
            "parts": [{"text": prompt_text}]
        }],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 16384,
            "topP": 0.9
        }
    }
    
    # Use GLOBAL location for gemini-3.5-flash (approved model only)
    url = f"https://aiplatform.googleapis.com/v1/projects/{project_id}/locations/global/publishers/google/models/{model}:generateContent"
    
    print(f"Endpoint: {url}")
    response = requests.post(url, headers=headers, json=payload, timeout=120)
    
    if response.status_code != 200:
        print(f"ERROR: Generation failed: {response.status_code}")
        print(response.text[:500])
        sys.exit(1)
    
    data = response.json()
    print(f"Response keys: {list(data.keys())}")
    
    generated_text = ""
    for candidate in data.get("candidates", []):
        for part in candidate.get("content", {}).get("parts", []):
            if "text" in part:
                generated_text = part["text"]
                break
    
    if not generated_text:
        print("ERROR: No text generated")
        print(f"Full response: {json.dumps(data, indent=2)[:500]}")
        sys.exit(1)
    
    print(f"✓ Generated {len(generated_text)} characters")
    return generated_text

def parse_generated_files(generated_text):
    """Extract file contents from generated code."""
    files = {}
    current_file = None
    current_content = []
    in_code_block = False
    
    for line in generated_text.split('\n'):
        # Detect file markers like "File: agents/prompt_id_coder_agent.py"
        if line.startswith('File:') or line.startswith('# File:'):
            if current_file:
                files[current_file] = '\n'.join(current_content).strip()
            current_file = line.split(':', 1)[1].strip()
            current_content = []
            in_code_block = False
        # Detect code blocks
        elif line.startswith('```'):
            in_code_block = not in_code_block
            if in_code_block and current_file:
                continue
        else:
            if current_file:
                current_content.append(line)
    
    # Save last file
    if current_file:
        files[current_file] = '\n'.join(current_content).strip()
    
    # Fallback: if no files detected, treat entire output as code
    if not files:
        print("⚠ No file markers detected. Using fallback parsing...")
        files['generated_code.txt'] = generated_text
    
    return files

def save_files(files_dict, output_base="."):
    """Save generated files to disk."""
    saved = []
    for filepath, content in files_dict.items():
        full_path = Path(output_base) / filepath
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content)
        saved.append(filepath)
        print(f"  ✓ {filepath} ({len(content)} bytes)")
    return saved

def main():
    parser = argparse.ArgumentParser(description="Automated Code Generator")
    parser.add_argument("--prompt-file", required=True, help="Prompt file to read")
    parser.add_argument("--output-dir", default=".", help="Output directory for generated code")
    parser.add_argument("--project-id", default="ctoteam", help="GCP project ID")
    parser.add_argument("--model", default="gemini-3.5-flash", help="LLM model to use")
    args = parser.parse_args()
    
    print(f"\n{'='*60}")
    print(f"AUTOMATED CODE GENERATOR (NO HUMAN IN LOOP)")
    print(f"{'='*60}")
    print(f"Prompt file: {args.prompt_file}")
    print(f"Output dir: {args.output_dir}")
    print(f"Model: {args.model}")
    print(f"Location: global")
    
    # Step 1: Read prompt
    print(f"\n[STEP 1] Reading prompt...")
    prompt_text = read_prompt(args.prompt_file)
    print(f"✓ Prompt loaded ({len(prompt_text)} chars)")
    
    # Step 2: Generate code
    print(f"\n[STEP 2] Generating code with Gemini...")
    generated = generate_code(prompt_text, args.project_id, args.model)
    
    # Step 3: Parse generated files
    print(f"\n[STEP 3] Parsing generated code...")
    files_dict = parse_generated_files(generated)
    print(f"✓ Found {len(files_dict)} file(s)")
    
    # Step 4: Save files
    print(f"\n[STEP 4] Saving generated files...")
    saved = save_files(files_dict, args.output_dir)
    
    # Summary
    print(f"\n{'='*60}")
    print(f"✅ CODE GENERATION COMPLETE")
    print(f"{'='*60}")
    print(f"Files generated: {len(saved)}")
    for f in saved:
        print(f"  - {f}")
    
    # Save generation report
    report = {
        "prompt_file": args.prompt_file,
        "model": args.model,
        "location": "global",
        "generated_chars": len(generated),
        "files_count": len(saved),
        "files": saved,
        "timestamp": subprocess.check_output(["date", "-u", "+%Y-%m-%dT%H:%M:%SZ"], text=True).strip()
    }
    report_path = Path(args.output_dir) / "generation_report.json"
    report_path.write_text(json.dumps(report, indent=2))
    print(f"\n✓ Report saved: {report_path}")

if __name__ == "__main__":
    main()
