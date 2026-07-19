# Setup

For a single end-to-end walkthrough (VPS install, every interface, growing
your own model), see `docs/GUIDE.md`. This document is the detailed
reference each section of that guide links back to.

## Before you put this on a real, reachable VPS

Read this before `python install.py` on a box with a public IP. None of
these are bugs — they're real, current tradeoffs, stated plainly rather
than discovered the hard way:

- **No built-in authentication.** Default (`local`) mode publishes the web
  GUI/API on `:8420` to whoever can reach that IP — there's no login, no
  API key, nothing beyond rate limiting (`docs/SETUP.md#rate-limiting`).
  Anyone who finds the port can chat with it, trigger skills (including
  outbound requests *from your VPS*, via `web_search`/`web_fetch`), and
  read `/audit`. **If this VPS is reachable beyond you personally, use
  `--tailscale`** (no public port at all — see below) instead of the
  default, or put your own authenticating reverse proxy in front of
  `:8420` if you specifically need public access.
- **Resource limits are a safety net, not a promise of good performance.**
  `docker-compose.yml`/`docker-compose.autopilot.yml` cap container memory
  (`KAFKAF_OLLAMA_MEM_LIMIT` default `8g`, `KAFKAF_BACKEND_MEM_LIMIT`
  default `2g`, `KAFKAF_AUTOPILOT_MEM_LIMIT` default `3g`) so a leak or
  runaway process gets OOM-killed inside its own container instead of
  taking down the whole host. If you switch to the `qwen3:14b` upgrade
  tier (see [Choosing your model](#choosing-your-model)), raise
  `KAFKAF_OLLAMA_MEM_LIMIT` to match — the default will OOM-kill Ollama
  under a model bigger than it expects.
- **Disk grows and nothing prunes it yet.** The audit log, conversation
  memory, and training corpus (`kafkaf.db`) all grow unboundedly — there's
  no automatic retention/rotation. Fine for normal use; worth an occasional
  `docker system df` / `du -sh` check on `/var/lib/docker/volumes/` if
  autopilot runs unattended for weeks, especially with a small VPS disk.
- **Confirmed by real verification, with one honest gap.** Every
  docker-compose overlay validates via `docker compose config`, every
  entrypoint has been exercised, and the actual own-model training loop
  has been run for real (see `docs/ROADMAP.md`'s phase 12). What has
  *not* been personally witnessed end-to-end in this project's own dev
  environment is a live `docker compose up` completing a real
  `ollama/ollama:latest` image pull — every attempt here hit that
  sandbox's own outbound-proxy restriction on Docker Hub, not anything
  in this repo. On a normal VPS with ordinary internet access this is a
  well-trodden path (a plain `docker pull`), but it's honest to say it
  wasn't watched succeed from this environment.

None of this means "don't install it" — it means: use `--tailscale`
unless you have a specific reason not to, know the memory tier you're
signing up for, and keep an eye on disk the way you would for any
long-running service.

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

## Autonomy levels

One legible dial (`--autonomy` at install time, or `KAFKAF_AUTONOMY_LEVEL`)
instead of remembering which combination of flags adds up to how much
KafKaf can do on its own. Percentages are an approximate framing, not a
literal slider — named tiers are harder to misconfigure than a raw number:

| Level | ~% | What it unlocks |
|---|---|---|
| `observe` | ~0% | Chat only. No tool use (skills mode is rejected at the API), no unattended growth loop. |
| `assisted` | ~50% | Skills (tools) available per chat turn. Autopilot does not start — a human still initiates any tool use or training. |
| **`autonomous`** (default) | ~100% | Skills available, **and** autopilot runs unattended by default. Everything currently shippable, with the real emergency stop (`kafkaf-autopilot-ctl stop`) as the safety valve that makes this default responsible. |

Set it at install time:
```
python install.py --autonomy assisted
```
Check what's active anytime: `kafkaf autonomy` or `GET /autonomy`. A
narrower override also exists — `--no-autopilot` keeps `autonomous`'s
skills enabled but skips just the autopilot container, if you want tools
without the unattended loop specifically.

**Change it live, no restart, from the web GUI** — the Control Panel's
Autonomy section has three buttons (Observe / Assisted / Autonomous);
picking one calls `POST /autonomy` and takes effect immediately for that
running process, including disabling the Skills checkbox in real time if
the new level doesn't allow it — the checkbox never contradicts what
`/chat` will actually do. Scope, honestly: this changes *this process*
only. It does not reach a separately-running `autopilot` Docker container
(that reads its own environment at startup), and it does not survive a
restart of this process unless `KAFKAF_AUTONOMY_LEVEL` is also updated —
use the live switch for "try a different level right now," and the env
var / `--autonomy` flag for "this is the level on every future start."

**Why a dial, not just more flags:** every capability KafKaf gains that a
human doesn't review turn-by-turn (autopilot's unattended cycles, in
particular) is a materially different kind of risk than one a human
explicitly triggers per chat. `observe`/`assisted`/`autonomous` makes that
distinction a single, visible setting instead of something you have to
reconstruct from several independent flags. There isn't a "beyond
autonomous" tier yet — the next one unlocks only once a capability with
that same "safe for a human-gated chat turn but not for the unattended
loop" shape (like sandboxed code execution — see `docs/ROADMAP.md`) has a
real answer for keeping it out of autopilot's reach, not just a flag that
says so.

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

**Language**: the עב/EN button in the header switches the whole UI between
Hebrew (RTL) and English (LTR) — never mixed, and the choice is
remembered (`kafkaf/clients/web/static/i18n.js`). **Theme**: the
☀️/🌙/🌅 button cycles Light / Dark / Auto. Auto tries a real local
sunset/sunrise calculation (via the browser's geolocation, computed
entirely client-side — no external API call) and falls back to your OS's
own light/dark preference if location isn't available or is denied.

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

Want "our own model" (the trainable, growing model — see
[#own-model--enrichment-mcp-server](#own-model--enrichment-mcp-server))
too? Install it up front, in the same command, instead of adding it later:

```
pip install -e ".[desktop-full]"   # desktop app + own-model training, one command
kafkaf-desktop
```

Doing it this way — one command, before ever launching the app — avoids
the Windows file-lock issue below entirely, since there's no second
`pip install` to run while the app is already open.

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

**Windows note: close the desktop app before reinstalling/upgrading.**
`pip install -e ".[...]"` rewrites the console-script wrapper
(`kafkaf-desktop.exe` in `Scripts/`) for every entry point, and Windows
won't let pip overwrite an `.exe` while its process is still running —
you'll see `OSError: [WinError 32] The process cannot access the file
because it is being used by another process`. Close the KafKaf window (or
`taskkill /IM kafkaf-desktop.exe /F`) before running `pip install` again,
whether that's adding an extra like `[train]` or pulling a new version.

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

**Self-maintaining identity**: every few training rounds (default 3,
`--identity-refresh-every N`, `0` disables) autopilot asks the current
teacher to fold the model's most recent training reflections into its
`identity.md` self-description — the same file the `identity` skill reads
and writes in chat — so the model's sense of "who it is and what it's
learned" stays current on its own, not only when someone asks. It
accumulates into the existing description rather than resetting it, and
like every other autopilot step it's driven by the capable teacher (never
the tiny model editing itself), caught if it fails so it can't kill the
loop, and recorded in the audit log.

The defaults are deliberately conservative, not "as fast as possible" — an
unattended loop hammering a paid API or a CPU flat-out is a cost/stability
risk, not a feature. Switching a teacher to `openai:`/`anthropic:`/
`gemini:` means every cycle involving it is a real, billed API call; know
that before turning the interval down or adding several paid teachers to
the rotation.

## Personas: different tone, same brain

A persona is just a system prompt + a name (`kafkaf/core/personas/`) —
picking one doesn't change which model answers, only how it's instructed
to. Three ship today:

| Persona | Key | Style |
|---|---|---|
| Kaf | `default` | Helpful, direct, honest about its own limits. |
| Researcher | `researcher` | Precise/technical, distinguishes fact from inference, cites specifics. |
| Coach | `coach` | Concise, ends with a clear next step, genuine (not generic) encouragement. |

Pick one:
- Web GUI: the persona dropdown next to the model dropdown.
- CLI: `kafkaf chat --persona researcher "..."` or `kafkaf repl --persona coach`.
- API: `POST /chat` with `{"persona": "researcher", ...}`.

An unknown persona key silently falls back to `default` rather than
erroring — see `kafkaf/core/personas/default.py`'s `get_persona()`.

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

The twenty-one skills that ship today, all working with no API key
required (`browser_render` additionally needs the optional `browser`
extra — see below the table):

| Skill | What it does |
|---|---|
| `web_search` | Search the web (DuckDuckGo, no key) |
| `web_fetch` | Fetch a URL's readable text (raw HTTP, no JS rendering) |
| `browser_render` | Render a JS-heavy page in a real, locked-down browser and return its visible text — for pages `web_fetch` can't read |
| `calculator` | Safe math evaluation (never `eval`/`exec`) |
| `current_datetime` | The current UTC date/time |
| `memory_search` | Search what the own model has already been taught |
| `files` | Read/write/list files in a sandboxed workspace |
| `document_search` | Keyword search over the *content* of files in that same workspace |
| `reminders` | A persistent reminder list (add/list/done) |
| `unit_convert` | Length/weight/temperature conversion |
| `rss` | Latest items from an RSS/Atom feed |
| `weather` | Current weather for a city (Open-Meteo, no key) |
| `system_info` | Read-only snapshot of the machine KafKaf itself runs on (OS, Python, CPU, disk) |
| `journal` | A private, timestamped notes log confined to the sandboxed workspace |
| `identity` | KafKaf's persistent self-description file — who it is, what it's learned about itself |
| `own_model_status` | How much the own model has learned so far — corpus size and last training run |
| `password_generator` | A cryptographically secure random password (Python's `secrets`, never a weak PRNG) |
| `text_diff` | Line-by-line differences between two pieces of text |
| `hash_text` | md5/sha1/sha256 of a piece of text |
| `random_pick` | Dice rolls or picking randomly from a list of options |
| `text_stats` | Word/character/sentence count and estimated reading time |

`browser_render` needs the optional `browser` extra, and a real browser
binary on top of that (a `pip install` alone isn't enough — same
two-step shape as `[train]`'s torch):
```
pip install -e ".[browser]"
playwright install chromium
```
Without this, the skill gives a clean error naming the exact command,
the same pattern as selecting the own model without `[train]` installed.
It's deliberately read-only: it never clicks, fills a form, or submits
anything (those Playwright APIs are simply never called), and it blocks
any navigation the page itself tries to trigger after the initial load —
the content it returns is always for the URL you gave it, nothing else.

The sandboxed workspace for the `files`, `document_search`, `journal`, and
`identity` skills defaults to `./workspace` — override with
`KAFKAF_SKILLS_WORKSPACE_DIR`, or point it at any real directory you
choose live from the web GUI's Control Panel ("Skills workspace
directory") — the same "you pick one working directory" model as Claude
Code's own working directory, not unrestricted access to the whole
machine. Whatever directory is set becomes the sandbox root; paths that
try to escape it (`../..`, absolute paths outside it) are still rejected
no matter where the root points. `document_search` is a small,
dependency-free "RAG-lite":
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

Skills mode combines with council mode — turn both on and every council
brain runs the tool-use loop independently before its answer is
synthesized (`{"council": true, "skills": true}`, or both toggles/flags at
once). See `docs/ARCHITECTURE.md` for how the underlying ReAct tool-use
loop works.

## Configuration

All settings are environment variables prefixed `KAFKAF_` (see
`kafkaf/core/config.py`):

| Variable                    | Default                   | Meaning                              |
|------------------------------|----------------------------|----------------------------------------|
| `KAFKAF_OLLAMA_HOST`         | `http://localhost:11434`  | Ollama API base URL                    |
| `KAFKAF_OLLAMA_MODEL`        | `qwen3:4b`                 | Model tag to use for chat — see [Choosing your model](#choosing-your-model) |
| `KAFKAF_AUTONOMY_LEVEL`      | `autonomous`                | `observe`/`assisted`/`autonomous` — see [Autonomy levels](#autonomy-levels) |
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
| `KAFKAF_OLLAMA_MEM_LIMIT`    | `8g`                        | Container memory cap for Ollama — raise if using the `qwen3:14b` tier |
| `KAFKAF_BACKEND_MEM_LIMIT`   | `2g`                        | Container memory cap for the backend    |
| `KAFKAF_AUTOPILOT_MEM_LIMIT` | `3g`                        | Container memory cap for the autopilot service |

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
