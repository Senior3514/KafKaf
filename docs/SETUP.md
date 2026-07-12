# Setup

For a single end-to-end walkthrough (VPS install, every interface, growing
your own model), see `docs/GUIDE.md`. This document is the detailed
reference each section of that guide links back to.

## One command, any OS (recommended)

Requires [Docker](https://docs.docker.com/get-docker/) — Linux, macOS, and
Windows (via Docker Desktop) all work identically since this is a plain
Python script, not a shell script:

```
python install.py
```

This brings up an `ollama` container plus the KafKaf `backend` container
(see `deploy/docker-compose.yml`), waits for Ollama to be ready, and pulls
the default model (`qwen3:4b` — override by setting `KAFKAF_OLLAMA_MODEL`
before running `install.py`; see
[Choosing your model](#choosing-your-model) below for which tag fits your
hardware). The backend — which also serves the web GUI — is then reachable
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
`ollama pull qwen3:4b` or whichever model you configure — see
[Choosing your model](#choosing-your-model)).

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

## Autopilot: unattended teach-and-train

`kafkaf-autopilot` (`kafkaf/core/enrichment/autopilot.py`) cycles through a
curriculum of topics, asks a teacher brain to explain each one, stores the
answer, and periodically runs a training step — the "lives on the VPS and
keeps growing on its own" piece. It shares the same corpus/checkpoint as
the backend and MCP server, so its progress shows up everywhere.

**Runs by default** — `python install.py` (or `deploy/install.sh`) starts
it automatically as its own container alongside the backend, sharing its
data volume. Pass `--no-autopilot` for a chat-only install instead:
```
python install.py --no-autopilot
```
or combine the overlay directly yourself:
```
docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.local.yml -f deploy/docker-compose.autopilot.yml up -d --build
```
Tune it with env vars *before* running the above (Compose bakes them into
the container's command at start time): `KAFKAF_AUTOPILOT_TEACHER` (default
`ollama:qwen3:4b` — free, local; **comma-separate multiple specs to
rotate through them**, e.g. `ollama:llama3,ollama:qwen3:4b,openai:gpt-4o-mini`
— different topics get taught by different models), `KAFKAF_AUTOPILOT_INTERVAL_SECONDS`
(default `300`), `KAFKAF_AUTOPILOT_TRAIN_EVERY` (default `5`),
`KAFKAF_AUTOPILOT_TRAIN_STEPS` (default `100`), and
`KAFKAF_AUTOPILOT_DYNAMIC_CURRICULUM` (set to `1` to let the teacher
propose new topics once the starting list runs out — see below). Watch it:
`docker compose -f deploy/docker-compose.yml logs -f autopilot`.

**Standalone** (no Docker):
```
pip install -e ".[train]"
kafkaf-autopilot --teacher "ollama:qwen3:4b,ollama:llama3" --interval-seconds 300 --dynamic-curriculum
```
Run `kafkaf-autopilot --help` for every option, including `--topics-file`
to teach it your own starting curriculum instead of the small built-in
default (`kafkaf/core/enrichment/topics.py`).

**Emergency stop**: full autonomy includes a real off switch. Autopilot
checks for a stop request every few seconds — including mid-sleep between
cycles, not just once per topic — so a stop takes effect almost
immediately, not after waiting out a full interval. Control a running
instance with the separate `kafkaf-autopilot-ctl` command:

```
kafkaf-autopilot-ctl stop      # halts a running autopilot within ~5s
kafkaf-autopilot-ctl status    # check whether a stop is currently requested
kafkaf-autopilot-ctl resume    # clear the stop so autopilot can start again
```

Both commands and `kafkaf-autopilot` itself operate on a shared stop-file
(`--stop-file`, default `autopilot.stop`) — `kafkaf-autopilot` refuses to
start while a stop is in effect, so `resume` first if you want to restart
after a real stop. **Via Docker**, the stop file lives on the shared
`/data` volume (`AUTOPILOT_STOP_FILE=/data/autopilot.stop`), so it survives
container restarts and is reachable from the host:
```
docker compose -f deploy/docker-compose.yml exec autopilot kafkaf-autopilot-ctl stop
```

**Dynamic curriculum**: with `--dynamic-curriculum`, once the starting
topic list is exhausted, autopilot asks the *current teacher* (a real,
capable model) to propose new topics that haven't been covered yet, and
keeps extending the list — the curriculum genuinely grows on its own over
time. This is the teacher generating what to learn next, not the small
owned model directing its own training (which is far too weak early on to
do that usefully) — an honest distinction worth keeping in mind.

The defaults are deliberately conservative, not "as fast as possible" — an
unattended loop hammering a paid API or a CPU flat-out is a cost/stability
risk, not a feature. Switching a teacher to `openai:`/`anthropic:`/
`gemini:` means every cycle involving it is a real, billed API call; know
that before turning the interval down or adding several paid teachers to
the rotation.

## Council: many models, one answer

Instead of picking one brain, council mode fans your question out to
*every* brain in `KAFKAF_COUNCIL_BRAINS` in parallel and synthesizes their
answers into one — real, working "get several models to help answer this,"
not just training. Set:

```
KAFKAF_COUNCIL_BRAINS=ollama:llama3,ollama:qwen3:4b
```

(add `openai:gpt-4o-mini`, `anthropic:claude-3-5-haiku-latest`,
`gemini:gemini-1.5-flash` if you've set the matching API key). Then use it
from any interface:

- Web GUI: the "מועצת מוחות" (council) toggle next to the model dropdown.
- CLI: `kafkaf chat --council "..."` or `kafkaf repl --council`.
- API: `POST /chat` with `{"council": true, ...}`.

If a brain in the list errors (bad key, network issue), it's just excluded
from that round — council mode only fails if *every* configured brain
fails. See `docs/ARCHITECTURE.md` for how the fan-out/synthesis works.

## Skills: giving the brain real tools

Skills mode lets a brain use tools mid-conversation instead of only
generating text — real web search, a calculator, files, reminders, and
more. Turn it on:

- Web GUI: the "סקילים" (skills) toggle next to the model dropdown.
- CLI: `kafkaf chat --skills "..."` or `kafkaf repl --skills`.
- API: `POST /chat` with `{"skills": true, ...}`.

The eleven skills that ship today, all working with no API key required:

| Skill | What it does |
|---|---|
| `web_search` | Search the web (DuckDuckGo, no key) |
| `web_fetch` | Fetch a URL's readable text |
| `calculator` | Safe math evaluation (never `eval`/`exec`) |
| `current_datetime` | The current UTC date/time |
| `memory_search` | Search what the own model has already been taught |
| `files` | Read/write/list files in a sandboxed workspace |
| `document_search` | Keyword search over the *content* of files in that same workspace |
| `reminders` | A persistent reminder list (add/list/done) |
| `unit_convert` | Length/weight/temperature conversion |
| `rss` | Latest items from an RSS/Atom feed |
| `weather` | Current weather for a city (Open-Meteo, no key) |

The sandboxed workspace for the `files` and `document_search` skills
defaults to `./workspace` — override with `KAFKAF_SKILLS_WORKSPACE_DIR`.
Paths that try to escape it (`../..`, absolute paths outside the workspace)
are rejected. `document_search` is a small, dependency-free "RAG-lite":
it chunks `.txt`/`.md`/`.rst`/`.csv`/`.json`/`.log` files by paragraph and
ranks chunks by keyword overlap — no vector DB or embeddings model, in
keeping with the project's minimal-dependency philosophy (the same spirit
as `calculator`'s hand-rolled safe eval). Drop files into the workspace
with the `files` skill's `write` command (or directly on disk), then
search their actual content instead of just their names.

**Not shipped on purpose**: raw code execution. A rushed, half-sandboxed
exec skill is a real security hole; it'll come once it's genuinely
isolated (subprocess + resource limits, or container isolation), not
before.

Skills mode and council mode are mutually exclusive for now — if both are
requested, council wins. See `docs/ARCHITECTURE.md` for how the underlying
ReAct tool-use loop works.

## Configuration

All settings are environment variables prefixed `KAFKAF_` (see
`kafkaf/core/config.py`):

| Variable                    | Default                   | Meaning                              |
|------------------------------|----------------------------|----------------------------------------|
| `KAFKAF_OLLAMA_HOST`         | `http://localhost:11434`  | Ollama API base URL                    |
| `KAFKAF_OLLAMA_MODEL`        | `qwen3:4b`                 | Model tag to use for chat — see [Choosing your model](#choosing-your-model) |
| `KAFKAF_DB_PATH`             | `kafkaf.db`                | SQLite path for memory + enrichment    |
| `KAFKAF_HOST`                | `0.0.0.0`                  | Backend bind host                      |
| `KAFKAF_PORT`                | `8420`                     | Backend bind port                      |
| `KAFKAF_OWN_MODEL_CHECKPOINT_PATH` | `kafkaf-own-model.pt`| Where the trained model is saved       |
| `KAFKAF_OWN_MODEL_PRESET`    | `tiny`                     | `tiny` (CPU-friendly) or `small` (GPU) |
| `KAFKAF_OPENAI_API_KEY`      | unset                      | Enables `openai:*` as a teacher        |
| `KAFKAF_ANTHROPIC_API_KEY`   | unset                      | Enables `anthropic:*` as a teacher     |
| `KAFKAF_GEMINI_API_KEY`      | unset                      | Enables `gemini:*` as a teacher        |
| `KAFKAF_COUNCIL_BRAINS`      | unset                      | Comma-separated brains for council mode |
| `KAFKAF_SKILLS_WORKSPACE_DIR` | `workspace`               | Sandboxed directory for the `files`/`document_search` skills |
| `KAFKAF_RATE_LIMIT_PER_MINUTE` | `120`                    | Requests/minute per client IP before `429` (`0` disables) |

## Choosing your model

`KAFKAF_OLLAMA_MODEL` picks the local Ollama model KafKaf chats with and (by
default) teaches its own model from. Three real, verified tags, picked by
available RAM/GPU — not tuned per app, just "what fits":

| Tier | Tag | Download size | Minimum RAM | When to use it |
|---|---|---|---|---|
| CPU-constrained fallback | `qwen2.5:3b` | 1.9GB | ~4GB | Old/weak hardware, or `qwen3:4b` is noticeably slow on your CPU |
| **Default (recommended)** | `qwen3:4b` | 2.5GB | ~8GB | Best speed/quality balance for most self-hosted setups — this is what `install.py`/`docker-compose.yml` pull by default |
| Upgrade tier | `qwen3:14b` | 9.3GB | ~16GB, or a GPU with 10GB+ VRAM | Meaningfully more capable; noticeably slower CPU-only |

Switch it before installing/starting:
```
KAFKAF_OLLAMA_MODEL=qwen3:14b python install.py
```
`install.py` reads the same env var when deciding which model to `ollama
pull`, so this actually changes what gets downloaded, not just what the
backend requests. Standalone/manual dev: `ollama pull qwen3:14b` then set
`KAFKAF_OLLAMA_MODEL` before `kafkaf-server`.

## Audit log: seeing what KafKaf actually did

Every chat turn (including which brain answered and how long it took),
every skill call, and every autopilot cycle is logged to a small SQLite
table (`kafkaf/core/audit/store.py`) — full autonomy is only trustworthy if
it's observable. Check it from any interface:

```
kafkaf audit                       # last 50 events
kafkaf audit --event-type skill    # only skill calls
```

or directly: `GET /audit?limit=50&event_type=chat`. Event types include
`chat`/`chat_council`/`chat_skills`, `skill`/`skill_error`, and
`autopilot_teach`/`autopilot_train`/`autopilot_curriculum_growth`/
`autopilot_stop`/`autopilot_error`. Not logged today: individual MCP tool
calls made outside a chat turn (e.g. calling `teach_fact` directly from
Claude Desktop) — a documented gap, not a silent one.

## Rate limiting

`KAFKAF_RATE_LIMIT_PER_MINUTE` (default `120`) caps requests per client IP
per minute on every route except `/health` and `/static/*`, returning `429`
once exceeded — an in-memory fixed-window limiter
(`kafkaf/core/rate_limit.py`), no Redis or extra service required. The
generous default assumes a single trusted user (or a small household/team
over Tailscale); set it lower if you want stricter protection, or `0` to
disable it entirely. This is not designed for a public multi-tenant
deployment — see `docs/ARCHITECTURE.md`.
