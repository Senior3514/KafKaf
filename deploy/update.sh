#!/usr/bin/env bash
# Pull the latest KafKaf code from the repo and rebuild/restart the running
# VPS deployment, in whichever mode (local/tailscale, +autopilot) it was
# installed with.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
MODE_MARKER="$SCRIPT_DIR/.compose-mode"
MODE="local"
AUTOPILOT=""
if [[ -f "$MODE_MARKER" ]]; then
  MODE="$(sed -n '1p' "$MODE_MARKER")"
  AUTOPILOT="$(sed -n '2p' "$MODE_MARKER")"
fi

FILES=("-f" "docker-compose.yml")
if [[ "$MODE" == "tailscale" ]]; then
  FILES+=("-f" "docker-compose.tailscale.yml")
  if [[ -z "${TS_AUTHKEY:-}" ]]; then
    echo "This deployment uses --tailscale mode; set TS_AUTHKEY before updating:" >&2
    echo "  TS_AUTHKEY=tskey-... ./deploy/update.sh" >&2
    exit 1
  fi
else
  FILES+=("-f" "docker-compose.local.yml")
fi
if [[ "$AUTOPILOT" == "autopilot" ]]; then
  FILES+=("-f" "docker-compose.autopilot.yml")
fi

echo "==> Pulling latest changes..."
(cd "$REPO_ROOT" && git pull --ff-only)

echo "==> Rebuilding and restarting KafKaf (mode: $MODE${AUTOPILOT:+, $AUTOPILOT})..."
(cd "$SCRIPT_DIR" && docker compose "${FILES[@]}" up -d --build)

if [[ "$MODE" == "tailscale" ]]; then
  echo "==> Updated. Reachable only on your tailnet (run: tailscale status)."
else
  echo "==> Updated. Backend: http://localhost:8420  (try: curl http://localhost:8420/health)"
fi
