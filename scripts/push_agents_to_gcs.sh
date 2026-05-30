#!/bin/bash

# Push agent files to GCS
# Usage: ./scripts/push_agents_to_gcs.sh <prompt_id> <project>
# Example: ./scripts/push_agents_to_gcs.sh 3381323161097207808 agentproject

PROMPT_ID=${1:-3381323161097207808}
PROJECT=${2:-agentproject}
GCS_PATH="gs://${PROJECT}/saved-prompts/${PROMPT_ID}/development/"

echo "Pushing agent files to GCS..."
echo "Project: $PROJECT"
echo "Prompt ID: $PROMPT_ID"
echo "Target GCS path: $GCS_PATH"
echo ""

# Files to push
FILES=(
    "agents/agent_gcs_puller.py"
    "agents/agent_ai_estimator.py"
    "agents/agent_code_developer.py"
    "agents/agent_code_quality_auditor.py"
    "scripts/run_agent_puller.sh"
    "scripts/run_agent_estimator.sh"
    "scripts/run_agent_developer.sh"
    "scripts/run_agent_auditor.sh"
    "scripts/run_all_agents.sh"
)

# Push each file
for file in "${FILES[@]}"; do
    if [ -f "$file" ]; then
        echo "Pushing: $file"
        gsutil cp "$file" "${GCS_PATH}$(basename $file)"
        if [ $? -eq 0 ]; then
            echo "✓ Successfully pushed: $file"
        else
            echo "✗ Failed to push: $file"
            exit 1
        fi
    else
        echo "✗ File not found: $file"
        exit 1
    fi
done

echo ""
echo "✓ All files pushed successfully to: $GCS_PATH"
