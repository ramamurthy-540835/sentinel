# PRISM Sentinel

PRISM Sentinel is a set of Python-based tools for **scientific AI development estimation**, requirements intelligence, and quality auditing of target projects.

It is designed to provide objective, traceable analysis without modifying the code under review.

---

## Getting Started

The easiest way to see what’s available is to run:

```bash
./start.sh
```

This script performs environment checks (ADC, GCP project) and prints the key workflows you can run.

---

## Main Capabilities

### 1. Scientific AI Development Estimation (Primary Focus)

This is the recommended workflow for understanding the effort, cost, and complexity of implementing a given Vertex AI Saved Prompt.

**Recommended flow for prompt `3381323161097207808`:**

```bash
# Step 1: Clean and classify the raw prompt (removes noise using deterministic + BQML rules)
./scripts/run_requirement_scope_extraction.sh 3381323161097207808

# Step 2: Run the scientific estimator (Gemini 3.5 Flash only)
./scripts/run_ai_development_estimator.sh 3381323161097207808 ../coder
```

**What it produces:**

- Clean requirement scope (`requirement_scope_clean.md`)
- Full scientific estimation report:
  - `reports/3381323161097207808/scientific_estimation.md`
  - `reports/3381323161097207808/scientific_estimation.json`

The estimator performs:
- Deterministic atomic requirement extraction
- Complexity classification (Simple / Medium / Complex)
- Functional Point calculation using fixed weights (Simple=3, Medium=5, Complex=8)
- Token & cost estimation using **only Gemini 3.5 Flash**
- Validation against actual code in the target directory (`../coder`)

---

### 2. Full Quality & Compliance Auditing

PRISM Sentinel can also run a complete quality audit against a target codebase.

```bash
# Run the full audit suite
./scripts/run_sentinel_all.sh ../coder --prompt-id 3381323161097207808 --write-bq
```

Individual audit steps are also available:
- `./scripts/run_requirement_mapping.sh`
- `./scripts/run_gap_analysis.sh`
- `./scripts/run_code_quality.sh`
- `./scripts/run_env_validation.sh`
- `./scripts/run_gcs_audit.sh`

**Audit reports** are written under `reports/`.

---

## Key Scripts

| Script                                      | Purpose                                      |
|---------------------------------------------|----------------------------------------------|
| `run_requirement_scope_extraction.sh`       | Clean & classify raw prompt (BQML + rules)   |
| `run_ai_development_estimator.sh`           | Scientific token/cost estimation             |
| `run_sentinel_all.sh`                       | Run complete quality audit suite             |
| `run_requirement_mapping.sh`                | Map requirements to code evidence            |
| `run_gap_analysis.sh`                       | Identify missing implementations             |
| `run_code_quality.sh`                       | Static analysis + policy checks              |

---

## Output Locations

- Estimation reports: `reports/<prompt_id>/scientific_estimation.{md,json}`
- Cleaned scope: `reports/<prompt_id>/requirement_scope_clean.md`
- All audit reports: `reports/`

---

## Project Focus

This directory (`sentinel/`) is the current primary home for:

- Scientific AI development estimation
- Prompt requirement intelligence
- Independent quality auditing

It is intentionally separate from other sub-projects in this workspace.

---

## Notes

- Most tools support the `--write-bq` flag to persist results to BigQuery.
- The tools prefer clean scope from the Requirement Intelligence layer when available.
- All estimation uses **Gemini 3.5 Flash only** (no other models).

For the most up-to-date commands, always run `./start.sh` first.