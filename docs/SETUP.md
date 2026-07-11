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

## Own model + enrichment MCP server

The MCP server lets you teach and train KafKaf's own model (see
`docs/ARCHITECTURE.md` for how it works) from Claude Desktop, Claude Code,
or any MCP client. It runs as a **local stdio process on your own
machine** — not a Docker service, since its entire purpose is direct local
integration with a desktop MCP client, and stdio has no network port or
auth surface to configure.

```
pip install -e ".[mcp,train]"
kafkaf-mcp
```

To use it from Claude Desktop, add it to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "kafkaf": {
      "command": "kafkaf-mcp"
    }
  }
}
```

Restart Claude Desktop, then try, in order: `teach_fact`, `train_step`,
`status`, `chat_with_own_model`. See `docs/ROADMAP.md` for the calibrated
expectation on quality — it starts weak and grows with use.

Optional: set API keys as env vars if you want `distill_from_teacher` to be
able to learn from API models, not just local Ollama models:
`KAFKAF_OPENAI_API_KEY`, `KAFKAF_ANTHROPIC_API_KEY`, `KAFKAF_GEMINI_API_KEY`.

Note: the MCP server and the Docker-based backend use the same SQLite file
by default (`KAFKAF_DB_PATH`) only if run on the same host without Docker.
If you dockerize the backend (`./deploy/install.sh`) and want the MCP
server (running on the host) to share its conversation/corpus data, point
`KAFKAF_DB_PATH` at a host path that's bind-mounted into the container —
the default `docker-compose.yml` uses a named volume, which isn't
host-addressable; that's a documented follow-up, not yet done.

## Configuration

All settings are environment variables prefixed `KAFKAF_` (see
`kafkaf/core/config.py`):

| Variable                    | Default                   | Meaning                              |
|------------------------------|----------------------------|----------------------------------------|
| `KAFKAF_OLLAMA_HOST`         | `http://localhost:11434`  | Ollama API base URL                    |
| `KAFKAF_OLLAMA_MODEL`        | `qwen2.5:3b`               | Model tag to use for chat              |
| `KAFKAF_DB_PATH`             | `kafkaf.db`                | SQLite path for memory + enrichment    |
| `KAFKAF_HOST`                | `0.0.0.0`                  | Backend bind host                      |
| `KAFKAF_PORT`                | `8420`                     | Backend bind port                      |
| `KAFKAF_OWN_MODEL_CHECKPOINT_PATH` | `kafkaf-own-model.pt`| Where the trained model is saved       |
| `KAFKAF_OWN_MODEL_PRESET`    | `tiny`                     | `tiny` (CPU-friendly) or `small` (GPU) |
| `KAFKAF_OPENAI_API_KEY`      | unset                      | Enables `openai:*` as a teacher        |
| `KAFKAF_ANTHROPIC_API_KEY`   | unset                      | Enables `anthropic:*` as a teacher     |
| `KAFKAF_GEMINI_API_KEY`      | unset                      | Enables `gemini:*` as a teacher        |
