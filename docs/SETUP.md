# Setup

## One command, any OS (recommended)

Requires [Docker](https://docs.docker.com/get-docker/) — Linux, macOS, and
Windows (via Docker Desktop) all work identically since this is a plain
Python script, not a shell script:

```
python install.py
```

This brings up an `ollama` container plus the KafKaf `backend` container
(see `deploy/docker-compose.yml`), waits for Ollama to be ready, and pulls
the default model (`qwen2.5:3b` — override by editing `DEFAULT_MODEL` in
`install.py` or setting `KAFKAF_OLLAMA_MODEL` before starting Ollama
manually). The backend — which also serves the web GUI — is then reachable
at `http://localhost:8420`.

Linux/macOS users who prefer a shell script can use `./deploy/install.sh`
instead; it does the same thing.

### Keeping a VPS deployment updated from the repo

```
./deploy/update.sh
```

Pulls the latest commit and rebuilds/restarts the Docker stack, using
whichever mode (`local`/`tailscale`) it was installed with (`install.py`
records this in `deploy/.compose-mode`).

## Tailscale access layer

By default (`python install.py`), the web GUI/API is published on the
host's public interface at `:8420` — fine for testing, but on a real VPS
you may not want port 8420 reachable by the whole internet. `--tailscale`
mode gives you a real access layer instead: the backend is reachable
**only** over your private [Tailscale](https://tailscale.com) network (a
tailnet) — no public port is published at all.

1. Get an auth key: Tailscale admin console → Settings → Keys → Generate
   auth key. A **reusable, tagged** key is the right choice for an
   unattended container (see
   [Tailscale's auth keys docs](https://tailscale.com/kb/1085/auth-keys)).
2. Run:
   ```
   TS_AUTHKEY=tskey-... python install.py --tailscale
   ```
3. KafKaf is now reachable only from devices on your tailnet, at an HTTPS
   URL Tailscale assigns automatically (MagicDNS), e.g.
   `https://kafkaf.<your-tailnet>.ts.net` — check `tailscale status` or the
   admin console for the exact address. Ollama's port also stays
   loopback-only regardless of mode; it's an internal dependency, never a
   public surface.

Under the hood: a `tailscale` sidecar container joins your tailnet, and the
`backend` container shares its network namespace
(`deploy/docker-compose.tailscale.yml`, the officially documented Tailscale
Docker Compose sidecar pattern) — so nothing is exposed until it's
explicitly proxied through Tailscale Serve. Updates
(`./deploy/update.sh`) automatically stay in this mode once installed this
way.

## Web GUI

Nothing to install — once the backend is running (Docker or
`kafkaf-server`), open `http://localhost:8420` in any browser. It's a
single static page (`kafkaf/clients/web/static/`) served directly by the
backend, mobile-first, no build step or Node toolchain.

## CLI / terminal

```
pip install -e .
kafkaf chat "hello"     # one-shot message
kafkaf repl              # interactive terminal session (type 'exit' to leave)
```

## Desktop app

A native window wrapping the same web GUI, built on
[pywebview](https://pywebview.flowrl.com/) (pure Python — no Electron/Node,
no Tauri/Rust toolchain), so it stays a single small dependency:

```
pip install -e ".[desktop]"
kafkaf-desktop
```

Pre-built single-file executables for Windows/macOS/Linux are produced by
`.github/workflows/build-desktop.yml` on every `v*` tag (or manually via
"Run workflow" in the Actions tab) — download them from that workflow
run's Artifacts. To build one yourself:

```
pip install -e ".[desktop]" pyinstaller
python scripts/build_desktop.py
```

The result is `dist/kafkaf-desktop` (`.exe` on Windows). **Linux note:**
pywebview's GTK backend needs system GObject-introspection bindings that
pip alone can't install — if `kafkaf-desktop` fails with "You must have
either QT or GTK", install them first: `sudo apt install python3-gi
python3-gi-cairo gir1.2-gtk-3.0 gir1.2-webkit2-4.1` (Debian/Ubuntu; see the
CI workflow for the exact package list). Windows (WebView2) and macOS
(WebKit) don't need any extra system packages — the OS provides the
webview engine.

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
