#!/usr/bin/env bash
# Linux/macOS shell twin of ../install.py, for the default (publicly
# published) mode. For no public exposure at all, use:
#   TS_AUTHKEY=tskey-... python ../install.py --tailscale
# KAFKAF_AUTONOMY_LEVEL selects observe/assisted/autonomous (default
# autonomous, see docs/SETUP.md#autonomy-levels). Autopilot runs by
# default at the autonomous level too — set KAFKAF_NO_AUTOPILOT=1 for a
# narrower override (autonomous, but no autopilot container).
set -euo pipefail

MODEL="${KAFKAF_OLLAMA_MODEL:-qwen3:4b}"
export KAFKAF_AUTONOMY_LEVEL="${KAFKAF_AUTONOMY_LEVEL:-autonomous}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

FILES=(-f docker-compose.yml -f docker-compose.local.yml)
AUTOPILOT_LABEL=""
if [[ "$KAFKAF_AUTONOMY_LEVEL" == "autonomous" && -z "${KAFKAF_NO_AUTOPILOT:-}" ]]; then
  FILES+=(-f docker-compose.autopilot.yml)
  AUTOPILOT_LABEL="autopilot"
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required. Install it first: https://docs.docker.com/engine/install/" >&2
  exit 1
fi

echo "==> Starting KafKaf stack (ollama + backend${AUTOPILOT_LABEL:+ + autopilot})..."
(cd "$SCRIPT_DIR" && docker compose "${FILES[@]}" up -d --build)

echo "==> Waiting for Ollama to be ready..."
until curl -sf http://localhost:11434/api/tags >/dev/null 2>&1; do
  sleep 2
done

echo "==> Pulling local model: $MODEL"
(cd "$SCRIPT_DIR" && docker compose "${FILES[@]}" exec -T ollama ollama pull "$MODEL")

printf 'local\n%s\n' "$AUTOPILOT_LABEL" > "$SCRIPT_DIR/.compose-mode"
echo "==> KafKaf is up (autonomy: $KAFKAF_AUTONOMY_LEVEL). Backend: http://localhost:8420  (try: curl http://localhost:8420/health)"
if [[ -n "$AUTOPILOT_LABEL" ]]; then
  echo "==> Autopilot running — stop anytime: docker compose -f docker-compose.yml exec autopilot kafkaf-autopilot-ctl stop"
fi
