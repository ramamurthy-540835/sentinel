#!/bin/bash
# Push agents and scripts to GCS development folder
set -euo pipefail

PROMPT_ID=${1:?ERROR: prompt_id required}
BUCKET=${2:-agentproject}

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR/.."

GCS_BASE="gs://${BUCKET}/saved-prompts/${PROMPT_ID}/development"

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║              PUSHING AGENTS TO GCS DEVELOPMENT FOLDER           ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "Target: $GCS_BASE"
echo ""

# Create development folder in GCS
echo "Creating GCS development folder..."
gsutil -m mb -c STANDARD "$GCS_BASE" 2>/dev/null || echo "Folder may already exist"

# Push agent files
echo ""
echo "Pushing Agent Python Files..."
gsutil -m cp agents/agent_gcs_puller.py "$GCS_BASE/agents/"
gsutil -m cp agents/agent_ai_estimator.py "$GCS_BASE/agents/"
gsutil -m cp agents/agent_code_developer.py "$GCS_BASE/agents/"

# Push script files
echo ""
echo "Pushing Shell Scripts..."
gsutil -m cp scripts/run_agent_puller.sh "$GCS_BASE/scripts/"
gsutil -m cp scripts/run_agent_estimator.sh "$GCS_BASE/scripts/"
gsutil -m cp scripts/run_agent_developer.sh "$GCS_BASE/scripts/"
gsutil -m cp scripts/run_all_agents.sh "$GCS_BASE/scripts/"

# Create manifest
MANIFEST="$GCS_BASE/MANIFEST.json"
echo ""
echo "Creating manifest..."
cat > /tmp/manifest.json << 'EOF'
{
  "version": "1.0",
  "created_date": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "agents": [
    {
      "name": "agent_gcs_puller",
      "description": "Fetches latest gold pointer and Silver layers from GCS",
      "file": "agents/agent_gcs_puller.py",
      "script": "scripts/run_agent_puller.sh"
    },
    {
      "name": "agent_ai_estimator",
      "description": "Generates architecture specification using Gemini 3.5 Flash",
      "file": "agents/agent_ai_estimator.py",
      "script": "scripts/run_agent_estimator.sh",
      "features": ["BigQuery token logging", "Gemini 3.5 Flash", "Token monitoring"]
    },
    {
      "name": "agent_code_developer",
      "description": "Executes code development based on estimator output",
      "file": "agents/agent_code_developer.py",
      "script": "scripts/run_agent_developer.sh"
    }
  ],
  "orchestrator": {
    "script": "scripts/run_all_agents.sh",
    "description": "Runs all 3 agents in sequence"
  },
  "execution": {
    "example": "bash scripts/run_all_agents.sh 3381323161097207808 gemini-3.5-flash agentproject",
    "notes": "Agents run sequentially. Each depends on previous output."
  }
}
EOF

gsutil cp /tmp/manifest.json "$MANIFEST"

# Create index file
echo ""
echo "Creating index file..."
INDEX="$GCS_BASE/INDEX.txt"
cat > /tmp/index.txt << 'EOF'
PRISM AGENT DEVELOPMENT PACKAGE
================================

STRUCTURE:
  agents/
    - agent_gcs_puller.py         (Agent 1: Fetch from GCS)
    - agent_ai_estimator.py       (Agent 2: Estimate with Gemini 3.5)
    - agent_code_developer.py     (Agent 3: Development executor)

  scripts/
    - run_agent_puller.sh         (Run Agent 1)
    - run_agent_estimator.sh      (Run Agent 2)
    - run_agent_developer.sh      (Run Agent 3)
    - run_all_agents.sh           (Orchestrator - runs all 3)
    - push_to_gcs.sh              (Deploy to GCS)

QUICK START:
  1. Clone from GCS to local machine:
     gsutil -m cp -r gs://agentproject/saved-prompts/3381323161097207808/development .

  2. Make scripts executable:
     chmod +x development/scripts/*.sh

  3. Run all agents:
     cd development
     bash scripts/run_all_agents.sh 3381323161097207808 gemini-3.5-flash

REQUIREMENTS:
  - Python 3.9+
  - Google Cloud SDK (gcloud)
  - google-cloud-storage
  - google-cloud-bigquery
  - GCP credentials (application-default login)

TOKEN MONITORING:
  All token usage is automatically logged to:
    BigQuery: ctoteam.agent_telemetry.token_usage

DEPLOYMENT:
  Transfer to 10.100.15.31:
    scp -r gs://agentproject/saved-prompts/3381323161097207808/development user@10.100.15.31:/path/to/prism/
EOF

gsutil cp /tmp/index.txt "$INDEX"

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                  🟢 PUSH COMPLETED SUCCESSFULLY                ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "GCS Location: $GCS_BASE"
echo ""
echo "Files pushed:"
echo "  ✓ agents/ (3 Python agents)"
echo "  ✓ scripts/ (4 shell scripts)"
echo "  ✓ MANIFEST.json"
echo "  ✓ INDEX.txt"
echo ""
echo "Download to development machine:"
echo "  gsutil -m cp -r \"$GCS_BASE\" ."
echo ""
