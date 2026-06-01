#!/usr/bin/env python3
"""
Basic incremental scope merger for Sentinel.

Usage:
  python3 scripts/merge_incremental_scope.py \
      --previous reports/<old-prompt>/requirement_scope_clean.json \
      --new-text "new prompt text or delta description" \
      --output reports/<prompt>/requirement_scope_clean.json

This is a first-step implementation: it appends new high-signal items
while preserving previous ones (no duplication of identical text).
"""
import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

def load_previous_scope(path: Path):
    if not path.exists():
        return {"previous_requirements": [], "clean_scope_text": ""}
    with open(path) as f:
        data = json.load(f)
    # Try to extract previous structured items if we add them later
    prev = data.get("structured_requirements", [])
    if not prev:
        # Fallback: split the clean text into lines as pseudo-requirements
        text = data.get("clean_scope_text", "")
        prev = [{"text": line.strip(), "source": "previous"} 
                for line in text.split("\n") if line.strip().startswith("- [")]
    return {"previous_requirements": prev, "raw": data}

def extract_new_high_signal(new_text: str, previous_texts: set):
    """Very simple deterministic high-signal extractor for new text."""
    lines = [l.strip() for l in new_text.split("\n") if l.strip()]
    new_items = []
    for line in lines:
        # Skip obvious noise
        if any(x in line.lower() for x in ["error", "traceback", "gsutil", "curl ", "select *"]):
            continue
        # Only keep reasonably meaty functional lines
        if len(line) > 25 and not line.startswith(("#", "-", "*")):
            if line not in previous_texts:
                new_items.append({
                    "text": line,
                    "category": "Functional",
                    "added_at": datetime.now(timezone.utc).isoformat(),
                    "source": "incremental_delta"
                })
    return new_items

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--previous", required=True, help="Path to previous requirement_scope_clean.json")
    parser.add_argument("--new-text", required=True, help="New prompt text or delta")
    parser.add_argument("--output", required=True, help="Output path for merged scope")
    args = parser.parse_args()

    prev = load_previous_scope(Path(args.previous))
    previous_texts = {r["text"] for r in prev["previous_requirements"]}

    new_items = extract_new_high_signal(args.new_text, previous_texts)

    # Build merged structured list
    merged = prev["previous_requirements"] + new_items

    # Build merged clean text (append new items)
    merged_text = prev.get("raw", {}).get("clean_scope_text", "")
    if new_items:
        merged_text += "\n\n# Incremental additions\n"
        for item in new_items:
            merged_text += f"- [{item['category']}] {item['text']}\n"

    result = {
        "package_uuid": prev.get("raw", {}).get("package_uuid"),
        "prompt_id": prev.get("raw", {}).get("prompt_id"),
        "model_target": prev.get("raw", {}).get("model_target"),
        "clean_scope_text": merged_text.strip(),
        "requirement_count": len(merged),
        "structured_requirements": merged,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "incremental": True,
        "previous_count": len(prev["previous_requirements"]),
        "new_items_added": len(new_items)
    }

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(result, f, indent=2)

    print(f"Merged scope written to {args.output}")
    print(f"Previous items: {len(prev['previous_requirements'])}")
    print(f"New items added: {len(new_items)}")
    print(f"Total now: {len(merged)}")

if __name__ == "__main__":
    main()
