#!/usr/bin/env bash
# start.sh – Dashboard opstarten (backend + optioneel frontend bouwen)
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
FRONTEND_DIR="$SCRIPT_DIR/frontend"
DIST_DIR="$FRONTEND_DIR/dist"

# ── Kleuren ────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'

echo -e "${GREEN}=== AI RC Car Dashboard ===${NC}"

# ── 1. Frontend bouwen als dist ontbreekt of --build meegegeven ──────────
if [[ "$1" == "--build" ]] || [[ ! -d "$DIST_DIR" ]]; then
  echo -e "${YELLOW}Frontend bouwen...${NC}"
  if ! command -v npm &>/dev/null; then
    echo -e "${RED}npm niet gevonden. Installeer Node.js >= 18.${NC}"
    exit 1
  fi
  (cd "$FRONTEND_DIR" && npm install && npm run build)
  echo -e "${GREEN}Frontend gebouwd: $DIST_DIR${NC}"
fi

# ── 2. Python vereisten installeren (in venv als aanwezig) ────────────────
if [[ -d "$SCRIPT_DIR/.venv" ]]; then
  source "$SCRIPT_DIR/.venv/bin/activate"
fi

if ! python3 -c "import fastapi" &>/dev/null; then
  echo -e "${YELLOW}Python pakketten installeren...${NC}"
  pip3 install -r "$BACKEND_DIR/requirements.txt" -q
fi

# ── 3. ROS2 sourcen als aanwezig ──────────────────────────────────────────
if [[ -f "/opt/ros/humble/setup.bash" ]]; then
  source /opt/ros/humble/setup.bash
  if [[ -f "$(dirname "$SCRIPT_DIR")/install/setup.bash" ]]; then
    source "$(dirname "$SCRIPT_DIR")/install/setup.bash"
    echo -e "${GREEN}ROS2 omgeving geladen.${NC}"
  fi
else
  echo -e "${YELLOW}ROS2 niet gevonden – mock modus actief.${NC}"
  export RC_PLATFORM=mock
fi

# ── 4. Backend starten ────────────────────────────────────────────────────
HOST="${DASHBOARD_HOST:-0.0.0.0}"
PORT="${DASHBOARD_PORT:-8080}"

echo -e "${GREEN}Dashboard starten op http://${HOST}:${PORT}${NC}"
echo -e "${GREEN}Druk Ctrl+C om te stoppen.${NC}"

cd "$BACKEND_DIR"
exec python3 -m uvicorn main:app \
  --host "$HOST" \
  --port "$PORT" \
  --log-level info
