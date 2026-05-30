#!/bin/bash
# Clear standard direct API keys to force native GCP Vertex AI authentication (ADC)
unset GEMINI_API_KEY
# Unset Google API Key to prevent direct Gemini API usage
unset GOOGLE_API_KEY
unset AIDER_GEMINI_API_KEY
unset AIDER_GOOGLE_API_KEY

set -euo pipefail

export GOOGLE_CLOUD_PROJECT="${GCP_PROJECT_ID:-ctoteam}"
export VERTEXAI_PROJECT="${GCP_PROJECT_ID:-ctoteam}"
export VERTEXAI_LOCATION="${VERTEXAI_LOCATION:-global}"
export GOOGLE_CLOUD_LOCATION="${GOOGLE_CLOUD_LOCATION:-global}"
export GOOGLE_REGION="${GOOGLE_REGION:-global}"

# =============================================
# EKF Aider Launcher - Dynamic Model Router
# Fully verified and loaded.
# =============================================

ENV_FILE="${ENV_FILE:-.env.local}"

# Dynamic project root resolution: Detect whether start_aider.sh is in root or scripts/
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/models.json" ]; then
  PROJECT_DIR="$SCRIPT_DIR"
else
  PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
fi

# Define log file with timestamp
LOG_FILE="$PROJECT_DIR/logs/aider_session_$(date +%Y%m%d_%H%M%S).log"

# Colors for output formatting
RED='\033[0;31m'
GREEN='\033[0;32m' # Green color for success messages
BLUE='\033[0;34m' # Blue color for headers
YELLOW='\033[0;33m'
NC='\033[0m' # No Color (reset)

echo -e "${BLUE}==================================================${NC}"
echo -e "${BLUE} 🚀 Mastech EKF Aider Launcher (Dynamic Router)   ${NC}"
echo -e "${BLUE}==================================================${NC}"

cd "$PROJECT_DIR"
# Ensure logs directory exists
mkdir -p logs

# Pre-flight dependency checks
check_dep() {
  if ! command -v "$1" &> /dev/null; then
    echo -e "${RED}❌ Missing required dependency CLI: $1${NC}" >&2
    exit 1
  fi
}
check_dep gcloud
check_dep bq
check_dep git
check_dep jq

if [ ! -f "$ENV_FILE" ]; then
  echo -e "${RED}❌ $ENV_FILE missing!${NC}"
  exit 1
fi

if [ ! -f "models.json" ]; then
  echo -e "${RED}❌ models.json missing!${NC}"
  exit 1
fi

set -a
source "$ENV_FILE"

# Model selection
MODEL_KEY="${1:-gemini-flash}"
MODEL_NAME=$(jq -r ".models.\"$MODEL_KEY\".api_model_id" models.json)
IS_SUPPORTED=$(jq -r ".models.\"$MODEL_KEY\".aider_supported" models.json)

if [ "$MODEL_NAME" = "null" ] || [ -z "$MODEL_NAME" ]; then
  echo -e "${RED}❌ Unknown model key: $MODEL_KEY${NC}"
  echo -e "Available: $(jq -r '.models | keys | join(", ")' models.json)"
  exit 1
fi

if [ "$IS_SUPPORTED" != "true" ]; then
  echo -e "${RED}❌ Model $MODEL_KEY is not supported with Aider.${NC}"
  echo -e "Use a model with aider_supported=true (e.g. gemini-flash)"
  exit 1
fi

DISPLAY_NAME=$(jq -r ".models.\"$MODEL_KEY\".display_name" models.json)
echo -e "${GREEN}💎 Starting Aider | Model: $DISPLAY_NAME ($MODEL_NAME)${NC}"

# Handle prompt file or phase argument
AIDER_EXTRA_ARGS=()
PROMPT_ARG="${2:-}"

# Execute aider
# Check if $PROMPT_ARG is passed and ends with .md or .py (is a prompt file)
if [ -n "$PROMPT_ARG" ]; then
  if [[ "$PROMPT_ARG" == *.md ]] || [[ "$PROMPT_ARG" == *.py ]]; then
    # Special case for long "build spec" prompt files: feed content as --message
    # so Aider executes the instructions instead of just opening the file for editing.
    if grep -qE '^(Goal:|Primary Inputs:|Create agents:|Acceptance:)' "$PROMPT_ARG" 2>/dev/null; then
      echo -e "${YELLOW}→ Detected build spec prompt. Sending content as initial message (not opening file).${NC}"
      exec aider --model "$MODEL_NAME" --no-auto-commits --message "$(cat "$PROMPT_ARG")"
    else
      exec aider --model "$MODEL_NAME" --no-auto-commits "$PROMPT_ARG"
    fi
  else
    exec aider --model "$MODEL_NAME" --no-auto-commits --message "$PROMPT_ARG"
  fi
else
  exec aider --model "$MODEL_NAME" --no-auto-commits
fi
