# Roadmap

## Vision — what "done" actually looks like

KafKaf's end-state is **a small, private, specialized language model that
you own, that runs entirely on your own hardware, and that keeps getting
better the more you teach and train it** — via facts you feed it directly,
via distillation from other models (local or API), and via the autopilot
curriculum loop that can run unattended on a VPS. Wrapped in interfaces
(web, desktop, CLI, MCP) that make talking to it and teaching it as easy as
talking to any other assistant.

This is **not** a path to AGI/ASI, and it never will be, no matter how long
it runs or how much it's taught. That's not a limitation of this particular
implementation — it's true of every system built this way, by anyone,
because "a small model taught more facts for longer" is not the same kind
of thing as general intelligence; there is no known way to get from one to
the other by scaling this loop. Saying otherwise would be marketing, not
engineering, and this project is built to be honest about what it actually
is. What it actually is — a growing, private, personal AI you fully
own — is a real and worthwhile thing to build, and it's what every phase
below is aimed at.

**This isn't asserted — it's checked against the literature.** Three
independent research passes (2026-07-12) converged on the same conclusion:

- *Scale.* Capability is a joint power-law function of parameters, data,
  and compute (Kaplan et al. 2020, arXiv:2001.08361; Hoffmann et al. 2022
  "Chinchilla," arXiv:2203.15556) — there's no training-time trick that
  substitutes for missing parameter count. Frontier training compute has
  grown ~4-5x/year and GPT-4-class runs use on the order of 2×10²⁵ FLOP
  (Epoch AI); a consumer GPU running flat-out for a full year reaches
  roughly 2.6×10²¹ FLOP — a gap of about four orders of magnitude, i.e.
  ~10,000x, that no amount of wall-clock time closes.
- *Continual learning.* Sequential training tends to overwrite prior
  knowledge (McCloskey & Cohen 1989's catastrophic interference; mitigated
  but not solved by Kirkpatrick et al. 2017's EWC, PNAS 114(13):3521-26).
  Distillation transfers what a teacher already knows, not new capability
  beyond it, and degrades further once the student/teacher capacity gap is
  too large (Hinton et al. 2015, arXiv:1503.02531; Mirzadeh et al. 2020,
  AAAI). A small model's ceiling is representational capacity, not elapsed
  training time.
- *Timelines and multi-agent systems.* The largest expert poll (Grace et
  al. 2024, arXiv:2401.02843, ~2,778 AI researchers) put the median
  estimate for human-level AI at 2047 with an enormous spread between
  respondents — genuine, unresolved uncertainty, not a roadmap. Frontier
  labs are explicit about this too (Anthropic's "Core Views on AI Safety"
  states difficulty "could lie anywhere on the spectrum from very easy to
  impossible"). Multi-agent orchestration (e.g. Wang et al. 2024
  "Mixture-of-Agents," arXiv:2406.04692) is documented as combining
  existing model capabilities — real, measurable, bounded gains — not a
  mechanism for producing new general intelligence beyond what the
  underlying models contain; coordination failures dominate as agent count
  grows (arXiv:2605.14892).

Full citation list and a readable summary: see the research memo linked
from PR #1, or ask for it to be regenerated.

KafKaf is built in phases; each one ships something runnable. No phase
depends on a big-bang release — "grow it over time."

- [x] **Phase 1 — Scaffolding**: repo layout, license, docs, base tooling.
- [x] **Phase 2 — Core loop end-to-end**: backend API + one local model
      (Ollama) + one persona + basic memory + thin CLI client. Works fully
      locally, zero API keys required.
- [x] **Phase 3 — Council (initial slice)**: `council.council_chat()` fans a
      query out to every brain listed in `KAFKAF_COUNCIL_BRAINS` in
      parallel (`asyncio.gather`), then synthesizes one final answer from
      whichever actually responded — the Mixture-of-Agents pattern (Wang et
      al. 2024): combining existing models' answers, not creating new
      general capability. Reachable via `/chat`'s `council: true`, `kafkaf
      chat --council` / `kafkaf repl --council`, and a web GUI toggle.
      Partial failures degrade gracefully (a brain that errors is just
      excluded, not fatal — see `docs/ROADMAP.md`'s multi-agent-systems
      citation on coordination failures for why this matters as brain count
      grows). Not yet done: a tool-use skills plugin system, multiple
      personas.
- [x] **Phase 4 — Web (mobile-first) + terminal**: a mobile-first web GUI
      (`kafkaf/clients/web/static/`) served directly by the backend — no
      build step, no separate deploy. `kafkaf repl` gives the CLI an
      interactive terminal session. Not yet done: a richer `textual`-based
      TUI (today's `repl` is a plain readline-style loop, which covers the
      "terminal" need but isn't a full TUI); a PWA manifest for
      installable/offline web use.
- [x] **Phase 5 — Desktop packaging**: `kafkaf/clients/desktop/` wraps the
      web GUI in a native window via `pywebview` (pure Python — chosen over
      Tauri specifically to avoid adding a Rust toolchain to the build).
      `.github/workflows/build-desktop.yml` builds single-file executables
      for Windows/macOS/Linux on every `v*` tag. Verified locally: the
      Linux build produces a working binary whose bundled backend + web GUI
      actually start and serve; the actual window can't be opened in a
      headless sandbox (no display), so real window-open behavior is only
      confirmed on real desktop OSes. Linux specifically needs system GTK
      bindings pywebview can't bundle standalone — see the caveat in
      `docs/SETUP.md`; Windows (WebView2) and macOS (WebKit) don't have
      this issue since the OS provides the engine.
- [x] **Phase 6 — Own-model training track**: a small transformer we design
      and pretrain ourselves (`kafkaf/model/` — byte-level nanoGPT-style
      GPT, no downloaded checkpoint), a corpus + continual-training loop
      (`kafkaf/core/enrichment/`), teacher brains for OpenAI/Anthropic/
      Gemini/Ollama (`kafkaf/core/brains/`), and a local MCP server
      (`kafkaf/mcp/server.py`, stdio, single-user) exposing `teach_fact`,
      `distill_from_teacher`, `train_step`, `status`, and
      `chat_with_own_model` — usable today from Claude Desktop/Code. The
      web GUI, CLI, and API can all also talk to it directly via an optional
      `brain` override (e.g. `kafkaf chat --brain own`), not just through
      MCP. **Unattended growth**: `kafkaf-autopilot`
      (`kafkaf/core/enrichment/autopilot.py`) cycles a curriculum of topics
      through a teacher and trains periodically, runnable standalone or as
      its own Docker service (`deploy/docker-compose.autopilot.yml`,
      `install.py --autopilot`) — deliberately paced, not "as fast as
      possible," since an unattended loop hammering a paid API or a CPU
      flat-out is a cost/stability risk. It can **rotate through multiple
      teacher models** (`--teacher "ollama:a,ollama:b,openai:gpt-4o-mini"`
      — "get several models in the market to train ours," genuinely, one
      topic at a time), and with `--dynamic-curriculum`, once the starting
      topic list is exhausted it asks the *current teacher* to propose new,
      non-duplicate topics and keeps growing — real autonomous curriculum
      expansion, honestly attributed to the teacher model (a capable
      brain), not the small owned model directing its own training, which
      would be far too weak to do anything coherent there. Not yet done:
      wiring `OwnModelBrain` into the council's default *routing* (it's
      reachable today via explicit override, just not chosen
      automatically), and a subword tokenizer upgrade.
- [x] **Phase 7 — Deployment automation + access layer**: `install.py` at
      the repo root is the one cross-platform install command (Linux/macOS/
      Windows, since it's Python rather than a shell script); `deploy/
      update.sh` pulls the latest commit and rebuilds/restarts a running VPS
      deployment in whichever mode it was installed with. `install.py
      --tailscale` gives a real private access layer — the backend is
      reachable only on your own tailnet, no public port at all
      (`deploy/docker-compose.tailscale.yml`, verified via `docker compose
      config` to merge correctly — no Docker daemon was available in the dev
      sandbox to run it live, so real tailnet connectivity is confirmed on
      first real use). Ollama's port is loopback-only in every mode. Not yet
      done: contribution docs for the public release, and the docker-compose
      named-volume → bind-mount fix noted in the phase 6 MCP section (only
      needed if the dockerized backend and a host-run MCP server must share
      one sqlite file).

## Notes on scope

- KafKaf does not claim to be AGI/ASI. It's an honest, practical, private,
  free AI agent platform — see the top of the main `README.md`.
- Model sizes in phases 2 and 6 assume no dedicated GPU is available yet.
  Once real hardware is confirmed, `deploy/docker-compose.yml`'s
  `KAFKAF_OLLAMA_MODEL` and the training config in phase 6 should be scaled
  up accordingly (bump `KAFKAF_OWN_MODEL_PRESET` from `tiny` to `small` —
  the same architecture, it just picks up a GPU automatically if one is
  available).
- **Calibrated expectation for the own-model track**: this is a genuine
  from-scratch training pipeline, not a trick — but a ~1-2M-param byte-level
  model trained for a few hundred CPU steps on a small corpus will show its
  training loss visibly decreasing (proof the pipeline works end-to-end)
  without sounding like a coherent assistant yet. That's expected. Quality
  grows only with many more `teach_fact`/`distill_from_teacher` +
  `train_step` calls over time, and faster once real GPU compute is
  available — "however long it takes, we grow it."
