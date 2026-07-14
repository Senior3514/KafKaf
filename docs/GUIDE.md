# The KafKaf Guide

Everything you need to install KafKaf on a VPS, talk to it from anywhere,
and grow your own model over time — start to finish, one document. Already
installed and just want day-to-day usage (not install)? See `docs/USAGE.md`
instead.

## What you're actually installing

KafKaf is a free, self-hosted AI platform that runs on your own machine or
VPS. Two things live inside it:

1. **A chat layer** on top of local open-source models (via
   [Ollama](https://ollama.com)) and, optionally, API models you bring your
   own key for. This part works immediately, out of the box.
2. **Your own small model** (`kafkaf/model/`) — a transformer we designed
   and that trains from your data, not a downloaded checkpoint. It starts
   knowing nothing and grows only from what you (or the autopilot loop,
   see below) teach and train into it.

**Read this once, seriously:** #2 will never become AGI or ASI, and
claiming otherwise would be dishonest marketing, not engineering. A small
model that's taught more facts for longer is not on a path to general
intelligence — there's no scaling trick that gets you there, and no one,
including labs with billions of dollars, has a known way to do it. What you
*are* building is real and worth having: a private, specialized, always-
improving assistant that's entirely yours. See `docs/ROADMAP.md`'s vision
section for the fuller version of this. This guide won't repeat the caveat
at every step, but it stays true throughout.

## 1. Install on your VPS

Requires [Docker](https://docs.docker.com/get-docker/). One command:

```bash
git clone <your fork/remote of this repo>
cd KafKaf
python install.py
```

That's it — Ollama and the KafKaf backend come up, the default model gets
pulled, and the web GUI is live at `http://<your-vps-ip>:8420`. **Autopilot
runs by default** — `kafkaf-autopilot` starts as a background container
that continuously teaches and trains your own model, unattended, the
moment you install — see [§4](#4-growing-your-own-model) below. A real
emergency stop is always one command away
(`kafkaf-autopilot-ctl stop`) — full autonomy always ships with a fast,
reliable off switch, never just "trust it."

**How much autonomy do you want?** One dial, `--autonomy`, controls it —
`autonomous` (default, above) has skills + autopilot both on;
`assisted` gives you tools per chat turn but no unattended loop; `observe`
is chat only:

```bash
python install.py --autonomy assisted    # skills, no autopilot
python install.py --autonomy observe     # chat only
```

Check what's active anytime with `kafkaf autonomy`. Full table:
`docs/SETUP.md#autonomy-levels`. (Narrower option: `--no-autopilot` keeps
`autonomous`'s skills on but skips only the autopilot container.)

**Want it private instead of public?** Use
[Tailscale](https://tailscale.com) as an access layer — no public port at
all, reachable only from your own devices (combines with `--no-autopilot`
if you want both):

```bash
TS_AUTHKEY=tskey-... python install.py --tailscale
```

(Get a key: Tailscale admin console → Settings → Keys → Generate auth key,
reusable + tagged. Full details in `docs/SETUP.md#tailscale-access-layer`.)

## 2. Talk to it — every interface

All of these are thin layers over the same backend; conversations and the
growing model are shared across all of them.

| Interface | How |
|---|---|
| **Web GUI** | Open the URL from step 1 in any browser. Use the model dropdown to switch between the default chat model and "your own" model, or the council/skills toggles for the modes below. |
| **CLI** | `pip install -e .` then `kafkaf chat "hello"` (one-shot) or `kafkaf repl` (interactive terminal session). Add `--brain own` to talk to your own model, `--council` to fan out to every `KAFKAF_COUNCIL_BRAINS` brain, or `--skills` to let it use tools. |
| **Desktop app** | `pip install -e ".[desktop]"` then `kafkaf-desktop` — a native window, same GUI. Or download a pre-built executable from the "Build desktop app" GitHub Actions workflow. |
| **API** | `POST /chat` with `{"message": "...", "brain": "own"}`, `{"council": true}`, or `{"skills": true}` — see `docs/ARCHITECTURE.md`. |
| **MCP** (Claude Desktop/Code) | `pip install -e ".[mcp,train]"` then `kafkaf-mcp`, wired into `claude_desktop_config.json` — see `docs/SETUP.md`. This is also how you manually teach/train (below), not just chat. |

**Council mode** — instead of one model answering, set
`KAFKAF_COUNCIL_BRAINS=ollama:llama3,ollama:qwen3:4b` (add API models if
you have keys) and every configured brain answers your question in
parallel; one gets synthesized into a final reply. Real, working
"get several models to help," not training — see `docs/SETUP.md`.

**Skills mode** — flip the skills toggle (or `--skills` / `{"skills": true}`)
and the brain can actually *use tools* mid-conversation instead of only
talking: real web search, a calculator, reading/writing sandboxed files,
searching what's actually written in those files (keyword "RAG-lite," no
vector DB), persistent reminders, unit conversion, RSS feeds, weather, and
searching what your own model has already been taught — eleven skills, all
working with no API key required. This is the ReAct pattern (ask a model to
act, not just answer), and it works the same way regardless of which brain
is answering. Combines with council mode too — turn both on and every
council brain gets independent tool access before synthesis. See
`docs/SETUP.md` for the full list and `docs/ARCHITECTURE.md` for how it
works under the hood.

## 3. Keep it updated from the repo

```bash
./deploy/update.sh
```

Pulls the latest commit and rebuilds/restarts in place, automatically
reusing whichever mode (`local`/`tailscale`, `+autopilot`) you installed
with.

## 4. Growing your own model

Two ways to teach it, and they compose — do both.

### Manually, via MCP

Connect `kafkaf-mcp` to Claude Desktop/Code (see `docs/SETUP.md`) and use:

- `teach_fact(topic, fact)` — tell it something directly.
- `distill_from_teacher(topic, teacher, instruction)` — ask another model
  (a local Ollama model, or OpenAI/Anthropic/Gemini if you've set an API
  key) to explain something, and store the answer as training data.
- `train_step(steps)` — actually train on what's been taught so far.
- `status()` — corpus size, last training run, checkpoint info.
- `chat_with_own_model(message)` — talk to it directly.

### Automatically, via autopilot

`kafkaf-autopilot` (running by default since step 1, or run standalone —
see `docs/SETUP.md`) cycles through a curriculum of topics, asks a teacher
to explain each one, and periodically runs a training step — unattended,
indefinitely. Defaults are **deliberately conservative**, not "as fast as
possible": one topic every 5 minutes, a training step every 5 topics, using
your local Ollama model as the teacher (free, no API cost). Tune it via env
vars before installing:

```bash
KAFKAF_AUTOPILOT_TEACHER=ollama:qwen3:4b \
KAFKAF_AUTOPILOT_INTERVAL_SECONDS=300 \
KAFKAF_AUTOPILOT_TRAIN_EVERY=5 \
KAFKAF_AUTOPILOT_TRAIN_STEPS=100 \
python install.py
```

**Many teachers, not just one** — comma-separate several specs and
autopilot rotates through them, one topic taught by a different model each
time: `KAFKAF_AUTOPILOT_TEACHER=ollama:llama3,ollama:qwen3:4b,openai:gpt-4o-mini`.
Switching in an API model (`openai:...`, `anthropic:...`, `gemini:...`)
means every cycle involving it makes a real, billed API call — fine
deliberately, but know that before turning the interval down or adding
several paid teachers.

**Curriculum that grows itself** — add `KAFKAF_AUTOPILOT_DYNAMIC_CURRICULUM=1`
and once the starting topic list is exhausted, autopilot asks the current
teacher to propose new, non-duplicate topics and keeps extending the list.
This is the teacher (a real, capable model) generating what to learn next
— not the small owned model directing its own training, which would be far
too weak early on to do anything coherent there. Worth being precise about
that distinction even as it gets more capable over time.

Customize the *starting* curriculum by pointing `topics_file` at your own
newline-separated list (one topic per line, `#` for comments) instead of
the small built-in default — see `kafkaf/core/enrichment/topics.py`.

**Emergency stop** — full autonomy means a real off switch. Run
`kafkaf-autopilot-ctl stop` (prefix with
`docker compose -f deploy/docker-compose.yml exec autopilot` if it's
running in Docker) and the loop halts within a few seconds — it checks for
a stop request continuously, not just between cycles. `kafkaf-autopilot-ctl
status` shows whether a stop is in effect; `kafkaf-autopilot-ctl resume`
clears it so autopilot can be started again. See `docs/SETUP.md` for the
full command reference.

### Calibrating expectations as it grows

Loss going down in `status()`/autopilot logs is proof the pipeline works.
Coherent, useful answers from `chat_with_own_model` take a lot more
teaching and training than a first session provides — that's expected, not
a bug. Scale up `KAFKAF_OWN_MODEL_PRESET` from `tiny` to `small` once real
GPU hardware is available (same architecture, no code changes).

## 5. Configuration reference

Full table of `KAFKAF_*` environment variables, API keys, and Tailscale
setup: `docs/SETUP.md`. Two worth knowing about specifically: `kafkaf audit`
shows exactly what KafKaf has actually done (every chat, skill call, and
autopilot cycle, with timing) — useful for trusting what an unattended
autopilot run did while you weren't watching; `KAFKAF_RATE_LIMIT_PER_MINUTE`
(default `120`) caps requests per client IP, `0` to disable. See
`docs/SETUP.md#audit-log-seeing-what-kafkaf-actually-did` and
`docs/SETUP.md#rate-limiting`.

## 6. Troubleshooting

- **`docker compose` fails with a `ports`/`network_mode` conflict** — you
  combined `docker-compose.local.yml` and `docker-compose.tailscale.yml`
  together; use exactly one of them (`install.py` never combines both).
- **Trained model gives gibberish** — expected at low corpus size / few
  training steps; see [§4](#4-growing-your-own-model)'s calibration note.
- **Desktop app won't open on Linux** — pywebview needs system GTK
  bindings; see the Linux note in `docs/SETUP.md`'s desktop section.
- **MCP server and the web GUI show different corpus/checkpoint state** —
  they need to point at the same `KAFKAF_DB_PATH`/checkpoint path; see the
  note at the end of `docs/SETUP.md`'s MCP section.
- **Something else** — `docs/ARCHITECTURE.md` has the full system map;
  `docs/ROADMAP.md` tracks what's built vs. planned.

## What's next

See `docs/ROADMAP.md` for the phased plan — a richer terminal UI, and
scaling the own-model track up as hardware allows. This is a "grow it over
time" project; this guide will grow with it.
