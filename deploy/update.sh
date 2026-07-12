#!/usr/bin/env bash
# Pull the latest KafKaf code from the repo and rebuild/restart the running
# VPS deployment, in whichever mode (local/tailscale) it was installed with.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
MODE_MARKER="$SCRIPT_DIR/.compose-mode"
MODE="local"
if [[ -f "$MODE_MARKER" ]]; then
  MODE="$(cat "$MODE_MARKER")"
fi

if [[ "$MODE" == "tailscale" ]]; then
  OVERLAY="docker-compose.tailscale.yml"
  if [[ -z "${TS_AUTHKEY:-}" ]]; then
    echo "This deployment uses --tailscale mode; set TS_AUTHKEY before updating:" >&2
    echo "  TS_AUTHKEY=tskey-... ./deploy/update.sh" >&2
    exit 1
  fi
else
  OVERLAY="docker-compose.local.yml"
fi

echo "==> Pulling latest changes..."
(cd "$REPO_ROOT" && git pull --ff-only)

echo "==> Rebuilding and restarting KafKaf (mode: $MODE)..."
(cd "$SCRIPT_DIR" && docker compose -f docker-compose.yml -f "$OVERLAY" up -d --build)

if [[ "$MODE" == "tailscale" ]]; then
  echo "==> Updated. Reachable only on your tailnet (run: tailscale status)."
else
  echo "==> Updated. Backend: http://localhost:8420  (try: curl http://localhost:8420/health)"
fi
