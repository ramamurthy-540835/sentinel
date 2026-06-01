# PRISM Sentinel - Quickstart

This guide shows the most common workflows when working in the `sentinel/` directory.

---

## 1. Start Here

Always begin by running:

```bash
cd /home/appadmin/projects/Ram_Projects/DiracDelta/sentinel
./start.sh
```

This performs environment checks and shows the available commands.

---

## 2. AI Development Estimation (Most Common Workflow)

For prompt `3381323161097207808`:

### Step 1: Clean the Prompt (Recommended)

```bash
./scripts/run_requirement_scope_extraction.sh 3381323161097207808
```

This produces a cleaned version of the prompt using deterministic + BQML classification.

**Output:**
- `reports/3381323161097207808/requirement_scope_clean.md`

### Step 2: Run Scientific Estimation

```bash
./scripts/run_ai_development_estimator.sh 3381323161097207808 ../coder
```

This performs:
- Deterministic requirement extraction
- Functional Point calculation
- Gemini 3.5 Flash token & cost estimation
- Validation against the actual code in `../coder`

**Main Outputs:**
- `reports/3381323161097207808/scientific_estimation.md`
- `reports/3381323161097207808/scientific_estimation.json`

---

## 3. Full Quality Audit

To run the complete Sentinel audit suite against a target:

```bash
./scripts/run_sentinel_all.sh ../coder --prompt-id 3381323161097207808 --write-bq
```

This runs:
- Requirement Mapping
- Gap Analysis
- Code Quality Review
- Environment Validation
- GCS Audit
- Audit Evidence Packaging

**Outputs:** All reports under `reports/`

---

## 4. Individual Commands Reference

| Command | Purpose |
|---------|---------|
| `./scripts/run_requirement_scope_extraction.sh 3381323161097207808` | Clean & classify prompt |
| `./scripts/run_ai_development_estimator.sh 3381323161097207808 ../coder` | Run full scientific estimation |
| `./scripts/run_sentinel_all.sh ../coder --prompt-id 3381323161097207808 --write-bq` | Run complete audit |
| `./scripts/run_gap_analysis.sh ../coder` | Gap analysis only |
| `./scripts/run_code_quality.sh ../coder` | Code quality review only |

---

## 5. Where to Find Results

All outputs are written under:

```
reports/3381323161097207808/
```

Key files:
- `scientific_estimation.md` — Human-readable estimation report
- `scientific_estimation.json` — Machine-readable version
- `requirement_scope_clean.md` — Cleaned prompt scope
- `audit_evidence_package.md` — Full audit summary (when running full audit)

---

## Tips

- The estimator prefers the cleaned scope (`requirement_scope_clean.md`) when available.
- Add `--write-bq` to most scripts to also write results to BigQuery.
- Run `./start.sh` anytime to see the current recommended commands.

---

**Next step:** Run `./start.sh` and follow the AI Estimation workflow for prompt `3381323161097207808`.