#!/usr/bin/env bash
# Pull the latest KafKaf code from the repo and rebuild/restart the running
# VPS deployment. Run this from a checkout that was set up with install.py /
# deploy/install.sh.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "==> Pulling latest changes..."
(cd "$REPO_ROOT" && git pull --ff-only)

echo "==> Rebuilding and restarting KafKaf..."
(cd "$SCRIPT_DIR" && docker compose up -d --build)

echo "==> Updated. Backend: http://localhost:8420  (try: curl http://localhost:8420/health)"
