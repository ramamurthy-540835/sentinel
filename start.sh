#!/usr/bin/env bash
#
# PRISM Sentinel - Development Environment Controller
#
# Usage:
#   ./start.sh                  # show status + workflows (default)
#   ./start.sh start            # start frontend (and any backend services)
#   ./start.sh stop             # stop services gracefully
#   ./start.sh restart          # stop + start
#   ./start.sh kill             # force kill using ss (by port)
#   ./start.sh status           # show current listening ports + processes
#

set -euo pipefail

# ─────────────────────────────────────────────────────────────────────────────
# Load environment (ports, host, etc.)
# ─────────────────────────────────────────────────────────────────────────────
if [ -f ".env.local" ]; then
  source .env.local
fi

# Defaults (can be overridden in .env.local)
FRONTEND_HOST="${FRONTEND_HOST:-10.100.15.31}"
FRONTEND_PORT="${FRONTEND_PORT:-3005}"
BACKEND_PORT="${BACKEND_PORT:-8005}"
HOST_IP="${HOST_IP:-10.100.15.31}"

PROJECT_ROOT="/home/appadmin/projects/Ram_Projects/DiracDelta"
UI_DIR="$PROJECT_ROOT/prompt-intelligence-ui"

# ─────────────────────────────────────────────────────────────────────────────
# Helper: Find PIDs listening on a port using ss
# ─────────────────────────────────────────────────────────────────────────────
get_pids_on_port() {
  local port=$1
  ss -tlnp 2>/dev/null | grep ":$port " | awk -F'pid=' '{print $2}' | cut -d',' -f1 | sort -u || true
}

# ─────────────────────────────────────────────────────────────────────────────
# Status
# ─────────────────────────────────────────────────────────────────────────────
show_status() {
  echo "▶ Sentinel services only (FRONTEND_PORT=$FRONTEND_PORT, BACKEND_PORT=$BACKEND_PORT)"
  echo "─────────────────────────────────────────────"

  # Sentinel Frontend
  if ss -tlnp 2>/dev/null | grep -q ":$FRONTEND_PORT "; then
    pids=$(get_pids_on_port "$FRONTEND_PORT")
    echo "  Frontend ($FRONTEND_PORT): RUNNING   (PIDs: $pids)"
    # Show which app is actually bound (very useful for debugging wrong frontends)
    for pid in $pids; do
      local cwd
      cwd=$(readlink /proc/$pid/cwd 2>/dev/null || echo "?")
      echo "    → $cwd"
    done
  else
    echo "  Frontend ($FRONTEND_PORT): NOT RUNNING"
  fi

  # Sentinel Backend
  if ss -tlnp 2>/dev/null | grep -q ":$BACKEND_PORT "; then
    pids=$(get_pids_on_port "$BACKEND_PORT")
    echo "  Backend  ($BACKEND_PORT): RUNNING   (PIDs: $pids)"
  else
    echo "  Backend  ($BACKEND_PORT): NOT RUNNING"
  fi

  echo ""
  echo "  (Other Next.js apps on 3000/3001/3002 etc. are ignored — sentinel-only mode)"
  echo ""
}

# ─────────────────────────────────────────────────────────────────────────────
# Kill processes on specific ports (force)
# ─────────────────────────────────────────────────────────────────────────────
kill_by_port() {
  local port=$1
  local pids
  pids=$(get_pids_on_port "$port")

  if [ -z "$pids" ]; then
    echo "  No process found listening on port $port"
    return 0
  fi

  echo "  Killing process(es) on port $port: $pids"
  for pid in $pids; do
    kill -9 "$pid" 2>/dev/null || true
  done
  sleep 1
}

# ─────────────────────────────────────────────────────────────────────────────
# Stop (graceful where possible)
# ─────────────────────────────────────────────────────────────────────────────
stop_services() {
  echo "▶ Stopping services on ports $FRONTEND_PORT and $BACKEND_PORT ..."

  # Try graceful first for Next.js (SIGTERM)
  for port in $FRONTEND_PORT $BACKEND_PORT; do
    pids=$(get_pids_on_port "$port")
    if [ -n "$pids" ]; then
      echo "  Sending TERM to port $port (PIDs: $pids)"
      for pid in $pids; do
        kill -TERM "$pid" 2>/dev/null || true
      done
    fi
  done

  sleep 2

  # Force kill anything still there
  for port in $FRONTEND_PORT $BACKEND_PORT; do
    kill_by_port "$port"
  done

  # Extra safety: also clean common wrong dev ports that users often leave running
  for rogue_port in 3000 8000; do
    if [ "$rogue_port" != "$FRONTEND_PORT" ] && [ "$rogue_port" != "$BACKEND_PORT" ]; then
      pids=$(get_pids_on_port "$rogue_port")
      if [ -n "$pids" ]; then
        echo "  Cleaning rogue process on port $rogue_port (PIDs: $pids)"
        for pid in $pids; do
          kill -9 "$pid" 2>/dev/null || true
        done
      fi
    fi
  done

  echo "  ✓ Services stopped"
}

# ─────────────────────────────────────────────────────────────────────────────
# Start
# ─────────────────────────────────────────────────────────────────────────────
start_services() {
  echo "▶ Starting services..."
  echo "   (Logs: /tmp/prompt-intelligence-ui.log  +  /tmp/sentinel_backend.log)"

  # Ensure key vars are exported
  export BACKEND_PORT FRONTEND_PORT HOST_IP FRONTEND_HOST
  export NEXT_PUBLIC_BACKEND_URL NEXT_PUBLIC_FRONTEND_URL DEFAULT_PROMPT_ID

  local start_log="/tmp/sentinel-start.log"
  echo "[$(date '+%F %T')] Starting services (FRONTEND=$FRONTEND_PORT, BACKEND=$BACKEND_PORT)" >> "$start_log"

  # Make the start function resilient (we don't want one failing ss/grep/whatever to abort the whole start)
  set +e

  # ── FRONTEND ────────────────────────────────────────────────────────────────
  echo "  Starting frontend on port $FRONTEND_PORT ..."

  # Always do a thorough clean before starting (this is the most reliable pattern)
  local pids
  pids=$(get_pids_on_port "$FRONTEND_PORT") || true
  if [ -n "$pids" ]; then
    echo "    Cleaning existing process(es) on $FRONTEND_PORT: $pids"
    for pid in $pids; do kill -9 "$pid" 2>/dev/null || true; done
    sleep 2
  fi
  pkill -f "next-server" 2>/dev/null || true
  sleep 1

  # Launch exactly as the project has always done
  (
    cd "$UI_DIR" || { echo "FATAL: UI_DIR missing: $UI_DIR" >> "$start_log"; exit 1; }
    nohup npx next dev --port "$FRONTEND_PORT" --hostname 0.0.0.0 \
      > /tmp/prompt-intelligence-ui.log 2>&1 &
    echo $! > /tmp/prompt-intelligence-ui.pid
  ) 2>> "$start_log" || true
  disown 2>/dev/null || true

  # Wait for the *correct* UI with good feedback
  echo -n "  Waiting for frontend (max 60s) "
  local fe_ok=false
  for i in {1..60}; do
    echo -n "."
    if grep -q "Ready in" /tmp/prompt-intelligence-ui.log 2>/dev/null; then
      local pid
      pid=$(get_pids_on_port "$FRONTEND_PORT" 2>/dev/null | head -1)
      if [ -n "$pid" ]; then
        local cwd
        cwd=$(readlink "/proc/$pid/cwd" 2>/dev/null || true)
        if [[ "$cwd" == *"prompt-intelligence-ui"* ]]; then
          fe_ok=true
          echo ""
          echo "  ✓ Frontend ready (PID $pid)"
          break
        fi
      fi
    fi
    sleep 1
  done

  if $fe_ok; then
    echo "  ✓ Frontend started: http://${FRONTEND_HOST}:${FRONTEND_PORT}"
    # Smoke test the endpoints the user actually cares about
    if curl -s --max-time 5 "http://127.0.0.1:${FRONTEND_PORT}/api/prompts" 2>/dev/null | python3 -c '
import sys,json
try:
  d=json.load(sys.stdin)
  if "prompts" in d: print("     /api/prompts OK (" + str(len(d.get("prompts",[]))) + " items)")
except: pass
' 2>/dev/null; then :; fi
  else
    echo ""
    echo "  ✗ Frontend did not become healthy on $FRONTEND_PORT"
    echo "     Last 25 lines of log:"
    tail -25 /tmp/prompt-intelligence-ui.log 2>/dev/null || true
    echo "     Current ss view:"
    ss -tlnp 2>/dev/null | grep -E '3005|next' || echo "     (nothing on 3005)"
    echo "[$(date '+%F %T')] FRONTEND FAILED" >> "$start_log"
  fi

  # ── BACKEND ────────────────────────────────────────────────────────────────
  echo "  Starting backend on port $BACKEND_PORT ..."

  pids=$(get_pids_on_port "$BACKEND_PORT") || true
  if [ -n "$pids" ]; then
    echo "    Cleaning existing process(es) on $BACKEND_PORT: $pids"
    for pid in $pids; do kill -9 "$pid" 2>/dev/null || true; done
    sleep 2
  fi

  (
    cd "$PROJECT_ROOT/sentinel" || exit 1
    BACKEND_PORT="$BACKEND_PORT" HOST_IP="$HOST_IP" \
      python3 -u sentinel_backend.py \
      > /tmp/sentinel_backend.log 2>&1 &
    echo $! > /tmp/sentinel_backend.pid
  ) 2>> "$start_log" || true

  echo -n "  Waiting for backend (max 25s) "
  local be_ok=false
  for i in {1..25}; do
    echo -n "."
    if ss -tlnp 2>/dev/null | grep -q ":$BACKEND_PORT "; then
      if curl -s --max-time 2 "http://127.0.0.1:${BACKEND_PORT}/health" 2>/dev/null | grep -q '"status": "ok"'; then
        be_ok=true
        echo ""
        break
      fi
    fi
    sleep 1
  done

  if $be_ok; then
    echo "  ✓ Backend started: http://${HOST_IP}:${BACKEND_PORT}"
    echo "     (pid: $(cat /tmp/sentinel_backend.pid 2>/dev/null || echo '?'))"
  else
    echo ""
    echo "  ✗ Backend did not become healthy on $BACKEND_PORT"
    echo "     Last 20 lines of /tmp/sentinel_backend.log:"
    tail -20 /tmp/sentinel_backend.log 2>/dev/null || true
    echo "     See full log: tail -100 /tmp/sentinel_backend.log"
    echo "[$(date '+%F %T')] BACKEND FAILED" >> "$start_log"
  fi

  echo ""
  echo "   Start attempt finished. Use './start.sh status' and 'ss -tlnp | grep -E 3005\|8005' to verify."

  set -e
}

# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────
case "${1:-}" in
  start)
    start_services
    ;;
  stop)
    stop_services
    ;;
  restart)
    stop_services
    sleep 1
    start_services
    ;;
  kill)
    echo "▶ Force killing processes on ports $FRONTEND_PORT and $BACKEND_PORT using ss..."
    kill_by_port "$FRONTEND_PORT"
    kill_by_port "$BACKEND_PORT"

    # Always aggressively kill any next-server (this is the #1 source of your port fights)
    echo "  Killing any next-server processes (rogue frontends)..."
    pkill -f "next-server" 2>/dev/null || true

    # Also aggressively clean common wrong ports (3000, 8000)
    for rogue_port in 3000 8000; do
      if [ "$rogue_port" != "$FRONTEND_PORT" ] && [ "$rogue_port" != "$BACKEND_PORT" ]; then
        pids=$(get_pids_on_port "$rogue_port")
        if [ -n "$pids" ]; then
          echo "  Force killing rogue process on port $rogue_port (PIDs: $pids)"
          for pid in $pids; do
            kill -9 "$pid" 2>/dev/null || true
          done
        fi
      fi
    done
    echo "  ✓ Done"
    ;;
  status)
    show_status
    ;;
  ""|help)
    # Default behavior: show nice banner + environment + workflows (original behavior)
    echo ""
    echo "╔════════════════════════════════════════════════════════════════════════════╗"
    echo "║                    PRISM SENTINEL — Development Environment                 ║"
    echo "╚════════════════════════════════════════════════════════════════════════════╝"
    echo ""

    # ADC Check (simplified)
    echo "▶ Checking ADC..."
    if gcloud auth application-default print-access-token &> /dev/null 2>&1; then
      echo "   ✓ ADC is configured"
      export NEXT_PUBLIC_ADC_STATUS="ok"
    else
      echo "   ⚠ ADC NOT CONFIGURED (some features will be degraded)"
      export NEXT_PUBLIC_ADC_STATUS="not_configured"
    fi

    echo ""
    echo "▶ Environment"
    echo "   Host / Frontend : ${FRONTEND_HOST}:${FRONTEND_PORT}"
    echo "   Backend         : ${FRONTEND_HOST}:${BACKEND_PORT}"
    echo "   Sentinel dir    : $(pwd)"
    echo ""

    show_status

    echo "════════════════════════════════════════════════════════════════════════════"
    echo "  AVAILABLE WORKFLOWS (Prompt: 3381323161097207808)"
    echo "════════════════════════════════════════════════════════════════════════════"
    echo ""
    echo "▶ 1. AI Estimation (Recommended)"
    echo "   ./scripts/run_requirement_scope_extraction.sh 3381323161097207808"
    echo "   ./scripts/run_ai_development_estimator.sh     3381323161097207808 ../coder"
    echo ""
    echo "▶ 2. Full Audit"
    echo "   ./scripts/run_sentinel_all.sh ../coder --prompt-id 3381323161097207808 --write-bq"
    echo ""
    echo "Useful commands:"
    echo "  ./start.sh start | stop | restart | kill | status"
    echo ""
    echo "Ready."
    ;;
  *)
    echo "Unknown command: $1"
    echo "Usage: $0 [start|stop|restart|kill|status]"
    exit 1
    ;;
esac
