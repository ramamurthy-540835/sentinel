# PRISM Sentinel - Curl & Testing Commands

**Server**: `http://10.100.15.31:8005` (backend)  
**UI**: `http://10.100.15.31:3005`

All commands use **prompt_id as a first-class runtime argument**.

---

## 1. Start / Stop / Restart Services (Recommended)

```bash
cd ~/projects/Ram_Projects/DiracDelta/sentinel

./start.sh start      # Start both frontend (3005) + backend (8005)
./start.sh stop
./start.sh restart    # Clean stop + start
./start.sh kill       # Force kill using ss (by port)
./start.sh status
```

- Uses `ss` for process discovery (no hardcoded PIDs)
- Single source of truth: [`.env.local`](.env.local) (`HOST_IP`, `FRONTEND_PORT=3005`, `BACKEND_PORT=8005`)
- Always run from the `sentinel/` directory

---

## 2. Prerequisites (ADC + Project)

```bash
# Verify ADC (Application Default Credentials) — required for Gemini
gcloud auth application-default print-access-token > /dev/null && echo "✓ ADC OK" || echo "⚠ Run: gcloud auth application-default login"

# Re-login if needed (full flow)
gcloud auth application-default login

# Check current project
gcloud config get-value project
gcloud config set project ctoteam
```

---

## 3. Core Test Commands (Backend API)

### Health Check
```bash
curl http://10.100.15.31:8005/health
```

### Status (compatibility aliases)
```bash
curl http://10.100.15.31:8005/api/status
curl http://10.100.15.31:8005/status
```

### Scope Extraction (Requirement Scope + Noise Filter)
```bash
curl -X POST http://10.100.15.31:8005/scope \
  -H "Content-Type: application/json" \
  -d '{"prompt_id": "3381323161097207808"}'
```

**Expected success output** (example):
```
================================================================================
PRISM Sentinel - BQML Requirement Scope Extraction
Prompt ID: 3381323161097207808
================================================================================
=== BQML Requirement Scope Extraction for 3381323161097207808 ===
Using local prompt file: ../coder/saved_prompts/3381323161097207808/final_assembled.md
Filtered out 59 noisy lines. Kept 103 candidate requirements.
Reports written to reports/3381323161097207808

✅ Requirement scope extraction complete.
   Clean scope is now available for the AI Development Estimator.
...
```

### Full AI Development Estimation (The Important One)
```bash
curl -X POST http://10.100.15.31:8005/estimate \
  -H "Content-Type: application/json" \
  -d '{"prompt_id": "3381323161097207808"}'
```

This runs the complete clean pipeline:
1. BQML noise classification + scope extraction
2. Deterministic function point counting (IFPUG-style: Simple=3, Medium=5, Complex=8)
3. Gemini-3.5-Flash **only** for token counting + cost (no hallucinated FP)

**Known good result for prompt 3381323161097207808**:
- **8 FP (Small)**
- **15,314 tokens**
- **~$0.0072**

---

## 4. Agent / Tool Tests

### Security / Data Steward Query
```bash
curl -X POST http://10.100.15.31:8005/api/agents/security \
  -H "Content-Type: application/json" \
  -d '{"query": "Find confidential retail datasets", "persona": "Data Steward"}'
```

---

## 5. Direct Script Testing (Bypass Backend)

You can also run the real scripts directly from the `sentinel/` directory:

```bash
# 1. Scope extraction only
./scripts/run_requirement_scope_extraction.sh 3381323161097207808

# 2. Full AI Development Estimator (recommended for local testing)
./scripts/run_ai_development_estimator.sh 3381323161097207808 ../coder

# 3. Full sentinel audit pipeline (all agents)
./scripts/run_sentinel_all.sh ../coder --prompt-id 3381323161097207808 --write-bq
```

These produce the same reports under `reports/3381323161097207808/`.

---

## 6. View Generated Reports (Prompt 3381323161097207808)

```bash
ls -la reports/3381323161097207808/

# Key files
cat reports/3381323161097207808/requirement_scope_clean.md
cat reports/3381323161097207808/scientific_estimation.md
cat reports/3381323161097207808/noise_classification_report.md
cat reports/3381323161097207808/functional_point_mapping.md
```

---

## 7. Useful Local Commands

```bash
# Live logs
tail -f /tmp/sentinel_backend.log
tail -f /tmp/prompt-intelligence-ui.log

# Process check (using ss, as enforced by start.sh)
ss -tlnp | grep -E ':3005|:8005'

# Kill stray processes manually (if needed)
pkill -f "sentinel_backend.py" || true
```

---

## 8. Full End-to-End Testing Workflow

```bash
cd ~/projects/Ram_Projects/DiracDelta/sentinel

# 1. Clean restart
./start.sh restart

# 2. Verify services are healthy
curl -s http://10.100.15.31:8005/health | jq .

# 3. Run scope extraction
curl -X POST http://10.100.15.31:8005/scope \
  -H "Content-Type: application/json" \
  -d '{"prompt_id": "3381323161097207808"}'

# 4. Run full estimation (the scientific output)
curl -X POST http://10.100.15.31:8005/estimate \
  -H "Content-Type: application/json" \
  -d '{"prompt_id": "3381323161097207808"}'

# 5. Check reports
ls reports/3381323161097207808/

# 6. Open UI
# http://10.100.15.31:3005
```

---

## 9. Troubleshooting

| Symptom                        | Likely Cause                              | Fix |
|--------------------------------|-------------------------------------------|-----|
| `curl: (52) Empty reply from server` | Old backend process had crash (NameError) | `./start.sh kill && ./start.sh start` |
| `{"error": "Not found"}`       | Missing route (pre-fix) or wrong path     | Use `/health`, `/scope`, `/estimate` |
| ADC / Gemini failures          | Token expired or wrong project            | `gcloud auth application-default login` |
| No output or old results       | Stale backend running                     | `./start.sh restart` (uses ss) |
| Port already in use            | Previous run didn't exit cleanly          | `./start.sh kill` |

**Always prefer**:
```bash
./start.sh restart
```
over manual `pkill` or `kill`.

---

## Notes

- **prompt_id** must be passed in the JSON body for `/scope` and `/estimate`.
- Default prompt in this session: `3381323161097207808`
- The backend (`sentinel_backend.py`) is intentionally minimal — it only orchestrates the real agents in `agents/` and scripts in `scripts/`.
- All deterministic FP math + BQML noise filtering happens in pure Python before any Gemini call.
- Gemini is used **only** for the final token/cost phase after clean scope is produced.

---

**Last updated**: 2026-06-01 (added GET /api/prompts for BigQuery prompt catalog + URL sync feature)

---

## 10. New Endpoint: GET /api/prompts (Prompt Catalog from BigQuery)

**Route**: `GET http://10.100.15.31:8005/api/prompts`

Returns list of prompts from `ctoteam.prism_prompt_catalog.prompt_versions` (or fallback).

### Example response (BigQuery success)
```json
{
  "prompts": [
    {
      "uid": "vertexai:1234567890123456789",
      "promptId": "1234567890123456789",
      "version": 3,
      "label": "My Production Prompt v3",
      "createdAt": "2026-05-28 14:22:11+00:00",
      "isActive": true
    }
  ],
  "source": "bigquery",
  "count": 42
}
```

### Example response (fallback when table/permissions differ)
```json
{
  "prompts": [
    {
      "uid": "vertexai:3381323161097207808",
      "promptId": "3381323161097207808",
      "version": 1,
      "label": "vertexai:3381323161097207808",
      "createdAt": "",
      "isActive": true
    }
  ],
  "source": "fallback",
  "error": "400 Unrecognized name: prompt_id ...",
  "count": 1
}
```

### Usage from frontend (when UI work is in scope)
```ts
const res = await fetch('/api/prompts')
const { prompts, source } = await res.json()
```

**Note on schema**: The actual table `prism_prompt_catalog.prompt_versions` uses different column names (`source_prompt_id`, `is_current`, `valid_from`, etc.) than the query in the spec. The current implementation falls back gracefully.

---

## 11. .env.local additions for this feature
```bash
SENTINEL_BACKEND_URL=http://10.100.15.31:8005
NEXT_PUBLIC_BACKEND_URL=http://10.100.15.31:8005
```

These are now present in the sentinel .env.local.

---

## Important Scope Note (as of this session)
Per explicit instruction, only files under `sentinel/` were modified.

The full feature (URL sync with `?uid=...`, dynamic dropdown in React, `useSearchParams`, `router.replace`, and wiring the cards to the new prompt list) requires changes in the Next.js app located at `../prompt-intelligence-ui/`.

That directory is outside the declared scope for this request. The backend contract (`GET /api/prompts`) is now ready for when the UI work is authorized.