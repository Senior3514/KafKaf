#!/usr/bin/env bash
set -euo pipefail

MODEL="${KAFKAF_OLLAMA_MODEL:-qwen2.5:3b}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required. Install it first: https://docs.docker.com/engine/install/" >&2
  exit 1
fi

echo "==> Starting KafKaf stack (ollama + backend)..."
(cd "$SCRIPT_DIR" && docker compose up -d --build)

echo "==> Waiting for Ollama to be ready..."
until curl -sf http://localhost:11434/api/tags >/dev/null 2>&1; do
  sleep 2
done

echo "==> Pulling local model: $MODEL"
(cd "$SCRIPT_DIR" && docker compose exec -T ollama ollama pull "$MODEL")

echo "==> KafKaf is up. Backend: http://localhost:8420  (try: curl http://localhost:8420/health)"
