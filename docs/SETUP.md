# Setup

## Docker (recommended)

Requires [Docker](https://docs.docker.com/engine/install/) with the Compose
plugin.

```
./deploy/install.sh
```

This brings up an `ollama` container plus the KafKaf `backend` container
(see `deploy/docker-compose.yml`), waits for Ollama to be ready, and pulls
the default model (`qwen2.5:3b` — override with `KAFKAF_OLLAMA_MODEL`).

Backend is then reachable at `http://localhost:8420`.

## Manual / local development

Requires Python 3.11+ and a locally running
[Ollama](https://ollama.com/download) (`ollama serve`, plus
`ollama pull qwen2.5:3b` or whichever model you configure).

```
pip install -e ".[dev]"
kafkaf-server        # starts the backend on :8420
```

In another shell:

```
kafkaf chat "hello"
pytest                # run the test suite (no Ollama required — tests use a fake brain)
```

## Configuration

All settings are environment variables prefixed `KAFKAF_` (see
`kafkaf/core/config.py`):

| Variable              | Default                   | Meaning                          |
|-----------------------|----------------------------|-----------------------------------|
| `KAFKAF_OLLAMA_HOST`  | `http://localhost:11434`  | Ollama API base URL               |
| `KAFKAF_OLLAMA_MODEL` | `qwen2.5:3b`               | Model tag to use for chat         |
| `KAFKAF_DB_PATH`      | `kafkaf.db`                | SQLite path for conversation memory |
| `KAFKAF_HOST`         | `0.0.0.0`                  | Backend bind host                 |
| `KAFKAF_PORT`         | `8420`                     | Backend bind port                 |
