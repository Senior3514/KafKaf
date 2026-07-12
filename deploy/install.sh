#!/usr/bin/env bash
# Linux/macOS shell twin of ../install.py, for the default (publicly
# published) mode. For no public exposure at all, use:
#   TS_AUTHKEY=tskey-... python ../install.py --tailscale
set -euo pipefail

MODEL="${KAFKAF_OLLAMA_MODEL:-qwen3:4b}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required. Install it first: https://docs.docker.com/engine/install/" >&2
  exit 1
fi

echo "==> Starting KafKaf stack (ollama + backend)..."
(cd "$SCRIPT_DIR" && docker compose -f docker-compose.yml -f docker-compose.local.yml up -d --build)

echo "==> Waiting for Ollama to be ready..."
until curl -sf http://localhost:11434/api/tags >/dev/null 2>&1; do
  sleep 2
done

echo "==> Pulling local model: $MODEL"
(cd "$SCRIPT_DIR" && docker compose -f docker-compose.yml -f docker-compose.local.yml exec -T ollama ollama pull "$MODEL")

echo "local" > "$SCRIPT_DIR/.compose-mode"
echo "==> KafKaf is up. Backend: http://localhost:8420  (try: curl http://localhost:8420/health)"
