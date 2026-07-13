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
      autopilot.py  # unattended curriculum loop (`kafkaf-autopilot`)
      topics.py      # default + custom curriculum for autopilot
    skills/       # tool use: a brain-agnostic ReAct loop + 10 real skills
      loop.py       # the ReAct protocol (see "Skills" section below)
      registry.py    # ALL_SKILLS / SKILLS_BY_NAME
      store.py        # persistence for the reminders skill
    db.py         # shared sqlite connection helper (memory + enrichment + skills)
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
  docker-compose.autopilot.yml    # overlay: unattended teach-and-train container
  install.sh                       # one-shot setup script (shell twin of ../install.py)
  update.sh                         # git pull + rebuild/restart, for a running VPS
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
  "have a web UI" are the same action — no separate frontend deploy. It's
  also an installable PWA: `manifest.json` + `sw.js` (a minimal
  cache-first-for-GETs service worker covering the app shell) let a phone
  "Add to Home Screen" it like a native app. `sw.js` is served from `GET
  /sw.js` (root), not `/static/sw.js` — a service worker's default scope is
  its own directory, so root-scoped is required for it to control `/`
  itself, not just `/static/*` requests.
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
to self-host, and it serves quantized open models (Qwen3, Qwen2.5, Llama 3,
Phi-4, Gemma, ...). The shipped default is `qwen3:4b`, chosen as the best
verified speed/quality balance for modest hardware (~8GB RAM, CPU-only is
fine) — see `docs/SETUP.md#choosing-your-model` for the full hardware-tiered
guide (a lighter CPU-constrained fallback and a heavier GPU/16GB+ upgrade
tier). API-backed models (Claude, GPT, etc., via a user-supplied key) are
meant to be opt-in extra brains later — never required for KafKaf to work.

## Personas

`core/personas/` (`Persona` — just a `key`, `name`, and `system_prompt`
dataclass) is deliberately trivial: picking a persona changes how a brain
is instructed, never which brain answers. `get_persona(key)` falls back to
`default` for an unknown key rather than erroring. Three ship today
(`default`/`researcher`/`coach` — see `docs/SETUP.md#personas-different-tone-same-brain`);
adding one is a new file plus a `PERSONAS` dict entry, nothing else in the
system needs to change.

## Council / multi-brain pattern

`core/council.py` is the single seam where a chat turn is resolved.
`handle_chat()` routes to one configured brain by default. **Council
mode** (`council_chat()`) fans the same messages out to every brain in a
configured list via `asyncio.gather` (partial failures are excluded, not
fatal — see `_gather_answers`), then asks a synthesizer brain to combine
whichever answers actually came back into one final reply. This is the
Mixture-of-Agents pattern (Wang et al. 2024, arXiv:2406.04692, cited in
`docs/ROADMAP.md`'s vision section) — an honest "ensemble of models"
version of "multiple brains," not a claim of general intelligence.

Configured via `KAFKAF_COUNCIL_BRAINS` (comma-separated specs, e.g.
`"ollama:llama3,ollama:qwen3:4b"`), triggered per-request: `/chat`'s
`council: true`, `kafkaf chat --council` / `kafkaf repl --council`, or the
web GUI's council toggle (which disables the brain dropdown — council mode
picks its own brains from config, not a single override). Combines with
skills mode — see below.

## Skills (tool use)

`core/skills/loop.py` implements ReAct (Yao et al. 2022, "ReAct:
Synergizing Reasoning and Acting in Language Models," arXiv:2210.03629): a
**text-protocol** tool-use loop, not a provider-specific function-calling
API. A brain is told (via a system-prompt preamble) it can respond with
`ACTION: <tool>: <argument>`; the loop executes that skill, feeds the
result back as `OBSERVATION: ...`, and repeats (capped at
`MAX_ITERATIONS`) until the brain responds with `FINAL ANSWER: ...`. This
is deliberately brain-agnostic — every `Brain.generate()` only ever
sees/returns plain text, so skills work the same way across Ollama, every
API brain, and eventually the small owned model, without touching the
`Brain` interface per provider.

`core/skills/registry.py` (`ALL_SKILLS`/`SKILLS_BY_NAME`) lists the eleven
shipped skills — `web_search` (DuckDuckGo HTML, no key), `web_fetch`,
`calculator` (safe `ast`-based evaluator, never `eval`/`exec`),
`current_datetime`, `memory_search` (queries the enrichment corpus),
`files` (read/write/list confined to `KAFKAF_SKILLS_WORKSPACE_DIR`, with
path-traversal rejected), `document_search` (keyword/paragraph-chunk
search over that same workspace's file *content* — no vector DB or
embeddings, just `re`-based tokenizing and overlap scoring, sharing the
sandboxing helper in `core/skills/sandbox.py` with `files`), `reminders`
(persistent, its own sqlite table via `core/skills/store.py`),
`unit_convert`, `rss`, and `weather` (Open-Meteo, no key). Each
`Skill.run()` takes and returns plain text — one argument, not multi-field
JSON — since small local models format that far more reliably than
structured calls.

Wired into `council.handle_chat()` as `use_skills: bool`. It combines with
council mode: `_gather_answers(brain_specs, messages, use_skills)` runs
each council brain through `run_skill_loop()` instead of a plain
`generate()` call when both are requested, so every brain in the fan-out
gets independent tool access before synthesis — a real combination of
"several models" and "each can use tools," not one silently overriding the
other. Reachable via `/chat`'s `skills: true`, `kafkaf chat --skills` /
`kafkaf repl --skills`, and a web GUI toggle (both toggles can be on at
once).

**Deliberately not shipped**: raw code execution. A hastily-sandboxed exec
skill is a real vulnerability, not a convenience — a properly isolated
version (subprocess with resource limits, or container isolation) is a
real follow-up, not something to rush.

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

`core/enrichment/autopilot.py` automates the teach → train loop
unattended: it cycles through a curriculum (`topics.py` — a small default,
or your own file) and a **rotation of teacher brains** (comma-separated
specs — different topics get taught by different models), calls
`distill_from_teacher` for each topic, and triggers `run_training_step`
every few topics. With `--dynamic-curriculum`, once the starting topic
list is exhausted, `propose_topics()` asks the current teacher to suggest
new, non-duplicate topics and the list keeps growing — the curriculum
expands on its own, driven by a real model. Runs as `kafkaf-autopilot`,
standalone or as its own Docker service
(`deploy/docker-compose.autopilot.yml`) sharing the backend's data volume.
Pacing defaults are conservative on purpose — see `docs/SETUP.md`.

A separate `kafkaf-autopilot-ctl` Typer app (`stop`/`resume`/`status`) is
the real emergency stop: `run_forever` checks a stop-file every
`STOP_POLL_SECONDS` (5s) via `_interruptible_sleep` — including mid-sleep
between cycles, not just once per topic — so a stop takes effect almost
immediately rather than after a full interval. `kafkaf-autopilot` itself
refuses to start while a stop file is present, so a real stop stays
stopped until explicitly resumed.

`core/api.py`'s `/chat` accepts an optional `brain` field (e.g. `"own"` or
`"ollama:llama3"`), resolved through the same registry, so any client (web
GUI's model dropdown, `kafkaf chat --brain own`) can talk to a specific
brain — including your own growing model — through the normal chat UI
instead of only via MCP.

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

## Audit log

`core/audit/store.py` follows the exact `_SCHEMA`/`_connect()` pattern of
`core/memory/store.py` — a single `audit_log` table recording every chat
turn (`council.handle_chat`), skill call (`skills/loop.py`'s
`run_skill_loop`), and autopilot cycle (`enrichment/autopilot.py`'s
`run_forever`), each with a duration and a short summary. `GET /audit` and
`kafkaf audit` are thin reads over it — no client talks to sqlite directly,
keeping the "thin client over one backend" principle from the top of this
document intact. Full autonomy (the autopilot loop, in particular) is only
trustworthy if what it did is visible after the fact; this is that record.
Scope is deliberately bounded: chat/skills/autopilot are logged, but MCP
tools called directly (e.g. `teach_fact` from Claude Desktop, outside a
chat turn) are not — a documented gap, not a silent one.

## Rate limiting

`core/rate_limit.py`'s `RateLimitMiddleware` (a `starlette.middleware.base.
BaseHTTPMiddleware`, zero new dependency since Starlette is already
transitive via FastAPI) is an in-memory, per-client-IP, fixed-window
limiter — no Redis, single process, matching the single-user/self-hosted
deployment model this whole document describes. It reads
`settings.rate_limit_per_minute` fresh on every request rather than caching
it at construction time, so it can be reconfigured without a restart (and
so it's monkeypatchable in tests). `/health` and `/static/*` are exempt.
This is explicitly not a multi-tenant-safe design — see
`docs/ROADMAP.md`'s deferred-work list for a real reverse-proxy gateway
pattern as a future upgrade if KafKaf is ever exposed beyond a single
trusted user/household.

## Autonomy levels

`core/autonomy.py` defines three named tiers (`observe`/`assisted`/
`autonomous`, `KAFKAF_AUTONOMY_LEVEL`, default `autonomous`) as the single
seam that governs how much KafKaf can do without a human reviewing each
step, instead of that judgment being scattered across independent flags.
`skills_allowed()` gates `/chat`'s `skills: true` (checked in `core/api.py`
before `council.handle_chat` is ever called — a 400 at `observe`, not a
silent no-op); `autopilot_default_on()` is read by `install.py`/`deploy/
install.sh` to decide whether the autopilot container is included at all.
`GET /autonomy` and `kafkaf autonomy` expose the current level and what it
unlocks, matching the audit log's "nothing about what KafKaf can do should
be a surprise" principle.

The tier boundary that matters most: `autonomous` is the ceiling for what
runs *unattended* (autopilot). A capability that's reasonable for a human
to trigger per chat turn but not for the unattended loop to reach on its
own — sandboxed code execution is the concrete example, see
`docs/ROADMAP.md` — doesn't get a green light just because
`--autonomy autonomous` is set; it needs its own, separate gate that
specifically keeps it out of autopilot's tool access, not just a higher
number on this dial.

## Privacy

Nothing leaves the machine running KafKaf unless a persona/query explicitly
opts into an API-backed brain, or an MCP `distill_from_teacher` call is
explicitly pointed at one. The default docker-compose stack talks only to
the local Ollama container. API keys for teacher models — and the Tailscale
auth key — are read only from environment variables, never hardcoded.
