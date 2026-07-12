# Architecture

One core backend API; every interface (CLI, terminal UI, desktop, web) is a
thin client over it. This avoids duplicating orchestration logic per client.

```
kafkaf/
  core/
    brains/       # adapters: local models (Ollama), API models (OpenAI/
                   # Anthropic/Gemini), our own trained model, + a registry
    council.py    # routes a chat turn to a brain (grows into multi-brain
                   # parallel routing + synthesis as more brains are added)
    personas/     # persona configs (system prompt, name)
    memory/       # persistent per-session conversation history (SQLite)
    enrichment/   # the training corpus + teach/distill/train orchestration
    db.py         # shared sqlite connection helper (memory + enrichment)
    api.py        # FastAPI app: /health, /chat, / (web GUI), /static
    server.py     # uvicorn entrypoint (`kafkaf-server`)
  clients/
    cli/          # thin CLI (typer) — talks to core/api.py over HTTP
    web/static/   # the web GUI itself (plain HTML/CSS/JS, served by core/api.py)
    desktop/      # pywebview wrapper around the web GUI -> packaged exe
    # tui/ — planned, see ROADMAP.md (kafkaf repl already covers "terminal" today)
  model/          # our own from-scratch-trained model (nanoGPT-style GPT,
                   # byte-level tokenizer, training loop) — see ROADMAP.md
  mcp/
    server.py     # local MCP server exposing enrichment tools over stdio
deploy/
  Dockerfile
  docker-compose.yml            # base: ollama + backend, no public ports
  docker-compose.local.yml       # overlay: publish backend on :8420 (default)
  docker-compose.tailscale.yml   # overlay: backend reachable only on your tailnet
  install.sh                      # one-shot setup script (shell twin of ../install.py)
  update.sh                        # git pull + rebuild/restart, for a running VPS
install.py         # the one cross-platform install command (Linux/macOS/Windows)
scripts/
  build_desktop.py  # builds the desktop app into a single-file exe (PyInstaller)
.github/workflows/
  build-desktop.yml  # CI: builds Windows/macOS/Linux exe on every v* tag
docs/
tests/
```

## Clients

All four interfaces are thin layers over the same `core/api.py` — no
orchestration logic is duplicated per client:

- **Web GUI** (`kafkaf/clients/web/static/`): plain HTML/CSS/JS, no build
  step, no Node toolchain. Served directly by the backend (`GET /` returns
  `index.html`, `/static/*` serves the rest) so "start the backend" and
  "have a web UI" are the same action — no separate frontend deploy.
- **CLI/terminal** (`kafkaf/clients/cli/main.py`, typer): `kafkaf chat` for
  one-shot messages, `kafkaf repl` for an interactive terminal session —
  both just POST to `/chat`.
- **Desktop app** (`kafkaf/clients/desktop/main.py`, pywebview): starts the
  same FastAPI backend in a background thread bound to `127.0.0.1` (loopback
  only), then opens a native OS window pointed at it. Packaged into a
  single-file executable per OS by `scripts/build_desktop.py` (PyInstaller)
  — see `.github/workflows/build-desktop.yml` and `docs/SETUP.md`. Chosen
  over Electron/Tauri specifically because it's pure Python — no separate
  Node or Rust toolchain needed to keep it buildable alongside the rest of
  the stack.
- **MCP server** — see its own section below; a different kind of client
  (an in-process tool surface for Claude Desktop/Code, not an HTTP client).

## Local model runtime

[Ollama](https://ollama.com) is the default local inference engine — simplest
to self-host, and it serves quantized open models (Llama 3, Qwen2.5, Phi-3,
Gemma2, ...). Pick the model size to match available RAM/VRAM; the default in
`deploy/docker-compose.yml` is a small model that runs reasonably on CPU.
API-backed models (Claude, GPT, etc., via a user-supplied key) are meant to be
opt-in extra brains later — never required for KafKaf to work.

## Council / multi-brain pattern

`core/council.py` is the single seam where a chat turn is resolved. Today it
routes to one configured brain. The intended growth path (see
`docs/ROADMAP.md`, phase 3) is: fan a query out to N configured brains in
parallel, then synthesize/rank the answers — an honest "ensemble of models"
version of "multiple brains," not a claim of general intelligence.

## Memory

`core/memory/store.py` is a small SQLite-backed conversation log, keyed by
`session_id`. It's intentionally simple for phase 2; a vector-store-backed
long-term memory is a natural phase-3+ upgrade once retrieval-augmented
recall is needed.

## Our own model + enrichment

`kafkaf/model/` is a small decoder-only transformer we design and train
ourselves — no `from_pretrained()`, no downloaded checkpoint. It's
byte-level (vocab_size=256), so there's zero tokenizer dependency and the
"tiny" preset stays genuinely tiny (~1-2M params, CPU-friendly). The same
architecture scales up via the "small" preset once real GPU hardware is
available (`torch.cuda.is_available()` is auto-detected, no code changes
needed).

`core/enrichment/` is the corpus + orchestration that feeds it, following
the exact storage pattern of `core/memory/store.py`:
- `teach_fact(topic, fact)` — store a raw human-provided fact.
- `distill_from_teacher(topic, teacher_brain, instruction)` — ask any
  configured `Brain` (a local Ollama model or an API model) to explain a
  topic, and store the captured answer as training data. The completion is
  always returned to the caller — enrichment is visible, never a blind
  ingestion.
- `run_training_step(steps)` — runs `kafkaf/model/train.py`'s training loop
  over unused corpus examples, continuing from the last checkpoint
  (continual learning: "teach and feed it").

`core/brains/registry.py` resolves a plain string ("ollama:llama3",
"openai:gpt-4o-mini", "anthropic:claude-3-5-haiku-latest",
"gemini:gemini-1.5-flash", or "own") into the matching `Brain` — the single
place that turns a "teacher" spec into a real model call, reused by the MCP
server below instead of duplicating model-calling code.

## Local MCP server

`kafkaf/mcp/server.py` exposes the enrichment flow as MCP tools
(`teach_fact`, `distill_from_teacher`, `train_step`, `status`,
`chat_with_own_model`) over **stdio** — the standard transport for local
Claude Desktop/Code integration. This is a deliberate architectural choice:
it runs as a separate host process from the FastAPI backend, so a slow
`train_step` call never blocks the live `/chat` API (there's no shared
event loop to starve). It is intentionally scoped to local/single-user use
— no network port, no auth surface. See `docs/SETUP.md` for how to point a
Claude Desktop config at it. It is **not** a Docker service — see
`docs/SETUP.md` for why.

## Access & networking

`deploy/docker-compose.yml` is a base file with no public ports at all —
it's always combined with one of two overlays (`install.py` picks
automatically):

- `docker-compose.local.yml` (default): publishes the backend on the host's
  `:8420`, same as a plain `docker run -p`.
- `docker-compose.tailscale.yml`: adds a `tailscale` sidecar container and
  gives the `backend` container `network_mode: service:tailscale` —
  publishes *nothing* to the host or the public internet. The backend is
  only reachable from devices on your own tailnet, via an HTTPS URL
  Tailscale assigns automatically (Tailscale Serve). This is the officially
  documented Tailscale + Docker Compose sidecar pattern, not a custom
  workaround. See `docs/SETUP.md` for setup.

Ollama's port is bound to `127.0.0.1` in the base file regardless of which
overlay is active — it's an internal dependency of the backend, never a
product surface, so there's no reason for it to ever be reachable from
outside the host.

`install.py` records which overlay was used in `deploy/.compose-mode` (git-
ignored, host-local state) so `deploy/update.sh` can rebuild in the same
mode without the flag needing to be remembered/re-passed.

## Privacy

Nothing leaves the machine running KafKaf unless a persona/query explicitly
opts into an API-backed brain, or an MCP `distill_from_teacher` call is
explicitly pointed at one. The default docker-compose stack talks only to
the local Ollama container. API keys for teacher models — and the Tailscale
auth key — are read only from environment variables, never hardcoded.
