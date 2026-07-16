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
      grows). **Skills (tool use)**: `kafkaf/core/skills/` implements the
      ReAct pattern (Yao et al. 2022, arXiv:2210.03629) — a text-protocol
      tool-use loop that works uniformly across every brain, not a
      provider-specific function-calling API. Ten real skills ship today:
      web search, web fetch, calculator, current date/time, memory search
      (the enrichment corpus), sandboxed file read/write, persistent
      reminders, unit conversion, RSS feeds, and weather — all either
      stdlib-only or free no-API-key services, so nothing needs a paid
      account to work. Deliberately **not** included: raw code execution —
      a rushed, half-sandboxed exec skill is a real security hole, worse
      than not having one; a properly isolated version (subprocess +
      resource limits, or container isolation) is a real follow-up, not a
      shortcut. Reachable via `/chat`'s `skills: true`, `kafkaf chat
      --skills` / `kafkaf repl --skills`, and a web GUI toggle. Both
      "not yet done" items noted here at the time — multiple personas, and
      combining skills with council mode in one turn — shipped in phase 11;
      see that entry for what changed and `docs/ARCHITECTURE.md` for the
      current (combinable) behavior.
- [x] **Phase 4 — Web (mobile-first) + terminal**: a mobile-first web GUI
      (`kafkaf/clients/web/static/`) served directly by the backend — no
      build step, no separate deploy. `kafkaf repl` gives the CLI an
      interactive terminal session. The PWA manifest noted here as "not yet
      done" shipped in phase 11 (`manifest.json` + `sw.js`). Still not yet
      done: a richer `textual`-based TUI (today's `repl` is a plain
      readline-style loop, which covers the "terminal" need but isn't a
      full TUI).
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
      **on by default** as of Phase 9 — `python install.py --no-autopilot`
      for a chat-only install) — deliberately paced, not "as fast as
      possible," since an unattended loop hammering a paid API or a CPU
      flat-out is a cost/stability risk. It can **rotate through multiple
      teacher models** (`--teacher "ollama:a,ollama:b,openai:gpt-4o-mini"`
      — "get several models in the market to train ours," genuinely, one
      topic at a time), and with `--dynamic-curriculum`, once the starting
      topic list is exhausted it asks the *current teacher* to propose new,
      non-duplicate topics and keeps growing — real autonomous curriculum
      expansion, honestly attributed to the teacher model (a capable
      brain), not the small owned model directing its own training, which
      would be far too weak to do anything coherent there. **Emergency
      stop**: a separate `kafkaf-autopilot-ctl` command (`stop`/`resume`/
      `status`) halts a running autopilot within seconds via a polled
      stop-file, not just at the end of a cycle — full autonomy always
      includes a real, fast off switch. Not yet done: wiring
      `OwnModelBrain` into the council's default *routing* (it's reachable
      today via explicit override, just not chosen automatically), and a
      subword tokenizer upgrade.
- [x] **Phase 7 — Deployment automation + access layer**: `install.py` at
      the repo root is the one cross-platform install command (Linux/macOS/
      Windows, since it's Python rather than a shell script); `deploy/
      update.sh` pulls the latest commit and rebuilds/restarts a running VPS
      deployment in whichever mode it was installed with. `install.py
      --tailscale` gives a real private access layer — the backend is
      reachable only on your own tailnet, no public port at all
      (`deploy/docker-compose.tailscale.yml`, verified via `docker compose
      config` to merge correctly; also attempted live in a later dev sandbox
      that did have a Docker daemon, where `python install.py` got as far as
      `docker compose up -d --build` before failing to pull the
      `ollama/ollama:latest` base image — that sandbox's outbound proxy
      blocks/expires Docker Hub's signed CloudFront blob URLs, a sandbox
      network-policy limitation, not a bug in `install.py` or the compose
      files; real tailnet/Docker-Hub connectivity is still confirmed on
      first real VPS use). Ollama's port is loopback-only in every mode.
      Contribution docs now ship as `CONTRIBUTING.md` (phase 11). Not yet
      done: the docker-compose named-volume → bind-mount fix noted in the
      phase 6 MCP section (only needed if the dockerized backend and a
      host-run MCP server must share one sqlite file).
- [x] **Phase 8 — Research-driven hardening and a knowledge-search skill**:
      a research pass comparing KafKaf against other self-hosted AI
      platforms (Open WebUI, LibreChat, LM Studio, Jan.ai, and others)
      surfaced concrete, in-scope improvements, built this phase: an
      eleventh skill, `document_search` (dependency-free "RAG-lite" —
      paragraph chunking + keyword-overlap scoring over the same sandboxed
      workspace the `files` skill writes to, no vector DB or embeddings
      model); the default local model upgraded from `qwen2.5:3b` to
      `qwen3:4b` after checking real, verified Ollama library tags and
      independent small-model benchmarks (not guessed), with a hardware-
      tiered "Choosing your model" guide in `docs/SETUP.md` (fallback /
      default / GPU-upgrade tiers) and a real bug fix so `install.py`
      actually honors `KAFKAF_OLLAMA_MODEL` when deciding what to `ollama
      pull` (previously hardcoded, silently inconsistent with what the
      backend would request); audit logging (`core/audit/store.py`, `GET
      /audit`, `kafkaf audit`) recording every chat turn, skill call, and
      autopilot cycle — full autonomy is only trustworthy if it's
      observable after the fact; and per-client-IP rate limiting
      (`core/rate_limit.py`, `KAFKAF_RATE_LIMIT_PER_MINUTE`, default `120`,
      `0` disables), an in-memory fixed-window limiter, zero new
      dependencies. Not yet done: semantic/embeddings-based search for
      `document_search` (deliberately deferred, not silently dropped — see
      below), and MCP-tool-level audit hooks (calling `teach_fact`/
      `train_step` directly from Claude Desktop, outside a chat turn, isn't
      logged today, only chat/skills/autopilot are).
- [x] **Phase 9 — Autonomy as the default posture**: `python install.py`
      (and `deploy/install.sh`) now run `kafkaf-autopilot` **by default** —
      KafKaf starts learning unattended the moment it's installed, not only
      when a `--autopilot` flag is remembered; `--no-autopilot` opts out for
      a chat-only install. This is deliberate: "grows on its own" should be
      what you get by default, with the emergency stop
      (`kafkaf-autopilot-ctl stop`, Phase 6) as the safety valve that makes
      that default responsible rather than reckless. **Considered and
      explicitly not shipped this phase**: a `run_python` code-execution
      skill (arbitrary Python via subprocess, timeout + memory limits, no
      inherited secrets, workspace-confined cwd — but not a container/
      seccomp sandbox, so no real network or absolute-path isolation beyond
      what the Docker container itself provides). Combined with autopilot
      now running unattended by default, giving the automated loop a path
      to execute arbitrary code is a materially different risk than the
      read/search/sandboxed-write skills shipped so far — flagged by this
      project's own tooling as a new RCE surface, and declined rather than
      rubber-stamped. Same status as before: a properly isolated version
      (real container/seccomp isolation, not just subprocess + rlimits) is
      a real future option, not a shortcut to take casually — see below.
- [x] **Phase 10 — A granular autonomy dial**: `core/autonomy.py` and
      `KAFKAF_AUTONOMY_LEVEL` (`--autonomy` at install time) replace "one
      binary autopilot flag" with three named, legible tiers —
      `observe` (~0%, chat only), `assisted` (~50%, skills available, no
      unattended loop), `autonomous` (~100%, the Phase 9 default: skills +
      autopilot both on). Enforced where it matters, not just documented:
      `core/api.py`'s `/chat` rejects `skills: true` at `observe` with a 400,
      and `install.py`/`deploy/install.sh` only include the autopilot
      container at `autonomous`. `GET /autonomy` / `kafkaf autonomy` show
      what's active. **Code execution, attempted a second time, declined a
      second time**: prompted to build it again with a real sandbox this
      round (bubblewrap/kernel-namespace isolation — no network namespace,
      read-only root, workspace-only writable — deliberately avoiding a
      Docker-socket-mounted approach, since giving the backend container
      access to the host Docker socket is itself a host-root-equivalent
      escalation path, a materially worse trade than the capability it would
      buy). Blocked again by this project's own tooling before any code was
      even installed, on the same grounds as Phase 9: general instructions
      to "give more autonomy/permissions" don't specifically name "let the
      unattended autopilot loop execute code" — the one shape of request
      this project treats as requiring an unambiguous, specific yes, not an
      inferred one. Two independent declines on the same capability is
      treated as a firm signal, not a threshold to route around with
      different tooling next time.
- [x] **Phase 11 — Personas, combined council+skills, and an installable
      web app**: three real personas now ship (`default`/`researcher`/
      `coach`, `core/personas/`), selectable from the web GUI's new
      dropdown, `kafkaf chat --persona`, or `/chat`'s `persona` field —
      closing the phase 3 "not yet done" item. **Skills now combine with
      council mode**, also closing a phase 3 item: `council.council_chat()`
      takes a `use_skills` flag, and when set, `_gather_answers()` runs
      every council brain through `run_skill_loop()` independently before
      synthesis — a real "several models, each with tools," not one flag
      silently overriding the other (`core/api.py`'s `skills` field no
      longer says "ignored if council=true," and the web GUI no longer
      disables the skills toggle when council is on). The web GUI is now an
      installable PWA — `manifest.json` + `sw.js` (cache-first for GETs
      only; `/chat`/`/audit` POSTs and always-fresh reads are never served
      stale), served from `GET /sw.js` at the root so its scope covers the
      whole app, not just `/static/*`. Icons are minimal generated PNGs
      (solid accent-color circle mark, no external image tooling available
      in the dev sandbox) — a real logo is an easy follow-up swap, not a
      blocker. `CONTRIBUTING.md` ships, closing the phase 7 "not yet done"
      item — codebase conventions (storage pattern, brain interface, skill
      shape, dependency philosophy) and an explicit note that
      security-sensitive capability requests need a specific, named
      description of the new capability and its blast radius, not a general
      "more autonomy" ask (see phase 9/10 for why that's a firm rule here,
      not boilerplate).
- [x] **Phase 12 — A full live verification pass, and a day-to-day usage
      guide**: everything merged through phase 11 was exercised live, not
      just asserted — the full test suite on merged `main`, every
      `pyproject.toml` entrypoint, all four docker-compose overlay
      combinations, the running backend server hit over real HTTP, and
      (the one that actually matters) the own-model pipeline run for real:
      `teach_fact` → `distill_from_teacher` → `run_training_step(30)` on a
      fresh checkpoint, loss `5.5664 → 3.3302`, then `chat_with_own_model`'s
      exact production routing path exercised end to end. Caught one real
      regression this way — a doc sentence phase 11 missed — fixed
      immediately rather than left stale. `docs/USAGE.md` also ships: a
      day-to-day usage guide (chat, personas/brain/council/skills,
      teaching the own model, `kafkaf autonomy`/`kafkaf audit`) distinct
      from `docs/GUIDE.md`'s install-focused walkthrough — the "how do I
      actually use this once it's running" gap didn't have a home before.
- [x] **Phase 13 — Accessibility pass and community health files**: the
      web GUI got a real (if scoped) accessibility pass, not just a
      cosmetic one — visible `:focus-visible` outlines on every
      interactive control that lacked one (`.brain-select`, `.send-btn`,
      the council/skills checkboxes), a proper (visually-hidden) `<label>`
      for the composer textarea instead of relying on a placeholder alone,
      `role="group"`/`aria-label` on the settings row, and a dedicated
      `--error` color token per theme so error bubbles have real contrast
      in dark mode instead of a fixed dark-red that washed out. `CODE_OF_
      CONDUCT.md` ships alongside `CONTRIBUTING.md` — standard community
      health coverage for a public repo, adapted to this project's actual
      voice rather than dropped in unedited.
- [x] **Phase 14 — A real bug, found by a real user, on a real machine**:
      `kafkaf-server` couldn't start with only `pip install -e ".[dev]"` —
      it required `torch` even though `torch` is explicitly a `[train]`-
      only extra everywhere else in this project (the Dockerfile's backend
      image is deliberately built without it; `enrichment/service.py`
      already lazy-imports `kafkaf.model.train` specifically to keep torch
      optional). The bug: `core/brains/registry.py` imported `OwnModelBrain`
      — which imports `kafkaf.model.gpt`, which imports `torch` — at module
      level, so *any* import of the registry (which `core/api.py` always
      does) pulled in torch unconditionally. This had been live and
      undetected through every "full verification pass" so far, because
      every test/dev environment in this project's own history happened to
      have `[train]` installed already. Found because a real user, on a
      bare Windows machine, ran the documented non-Docker path exactly as
      written and hit `ModuleNotFoundError: No module named 'torch'`.
      Fixed by moving the `OwnModelBrain` import into `get_brain()`'s
      `"own"` branch (matching the already-established lazy-import pattern
      in `enrichment/service.py`), plus a regression test
      (`test_registry_and_api_import_without_torch_installed`) that
      actually blocks `torch` from being importable and confirms
      `core.api` and every non-`"own"` brain still work. The lesson worth
      keeping: a verification pass is only as good as the environment
      diversity behind it — this one's dev/CI environment always had every
      optional extra installed, so a real gap in the *documented default
      install path* survived several rounds of "everything passes."
- [x] **Phase 15 — Another real bug from real usage, plus a genuine i18n
      pass**: the same live-testing user hit a second real bug once
      phase 14 unblocked them — `/chat` only caught `RuntimeError`, so any
      other failure (Ollama unreachable, model not pulled, a network
      error) propagated as an unhandled exception, which FastAPI turns
      into a raw HTML 500 page; the web GUI always calls
      `response.json()`, so the failure showed up client-side as a
      confusing `Unexpected token 'I', "Internal S"... is not valid JSON`
      instead of a real error message. Fixed with a broad `except
      Exception` in `core/api.py`'s `/chat` returning a proper JSON 502
      with a helpful message ("is Ollama running and is the model
      pulled?"), covered by a test that actually raises inside a fake
      brain and asserts a parseable JSON error comes back. Live-verified
      with Playwright against the real running server (not just unit
      tests): the exact "Unexpected token" failure mode is now gone.

      Also shipped, from the same conversation's UI feedback: a real
      language toggle (`kafkaf/clients/web/static/i18n.js`) — Hebrew and
      English are no longer mixed in the same view; the whole UI (labels,
      placeholders, aria-labels, `dir`/`lang` on `<html>`) switches
      together via one button, choice persisted. A light/dark/auto theme
      toggle, where **auto is a real local sunset/sunrise calculation**
      (the well-known "Sunrise Equation" from the 1990 Almanac for
      Computers, computed client-side from `navigator.geolocation` — no
      external API — falling back to `prefers-color-scheme` if location
      is unavailable/denied), not just a rebrand of the OS preference.
      Found and fixed in the process: `.bubble.user`/`.bubble.assistant`'s
      chat-tail corners were hardcoded to physical `border-bottom-left-
      radius`/`-right-radius`, which is only correct in one text direction
      — switched to logical properties (`border-end-end-radius`/`-start-
      radius`) so the tail stays on the right corner in both RTL and LTR
      automatically. All of it live-verified with a real headless-browser
      session against the real server: default Hebrew/RTL, the language
      toggle actually flipping `dir`/`lang`/labels, bubble alignment
      correct on both sides, and light vs. dark mode producing genuinely
      different rendered colors — not just asserted, screenshotted.
- [x] **Phase 16 — Onboarding clarity and a real in-app Control Panel**:
      the same live-testing user hit a third real friction point after
      phases 14-15 unblocked them — not a bug in the code, but a bug in
      *communication*. Chat prose describing "run `pip install -e
      ".[desktop]"` then `kafkaf-desktop`" used "then" as an English
      connecting word between two separate commands; copy-pasted literally
      into PowerShell, it tried (and failed) to `pip install` a package
      named `then`. `docs/GUIDE.md`'s interface table had the identical
      inline phrasing (unlike `docs/USAGE.md`, which already used a proper
      two-line code block). Separately, the user didn't know
      `kafkaf-desktop` starts its own backend automatically — they assumed
      (reasonably, since nothing said otherwise) that `kafkaf-server` had
      to be running in a second window first. Fixed: every "run X, then
      run Y" description in `docs/GUIDE.md` is now an explicit two-command
      table row with a "these are separate commands" callout, plus a new
      "The absolute short version" section at the very top of the guide
      explaining the engine/window distinction in plain terms before any
      other detail; `docs/USAGE.md`'s desktop-app paragraph now says
      explicitly that `kafkaf-desktop` is self-contained and you pick one
      interface, not both.

      Also shipped, from the same message's "we want full control and full
      configuration" ask: a real **Control Panel** in the web GUI (🎛️
      button) — a new `GET /status` endpoint (`core/api.py`) surfacing
      current autonomy level + description + whether skills are allowed,
      own-model training progress (corpus size, examples still waiting to
      be trained, whether a checkpoint exists, the last training run), and
      the 8 most recent `/audit` events, all rendered live in a themed,
      translated, RTL/LTR-correct modal. This doesn't add new autonomy
      *capabilities* — autonomy levels, autopilot, and manual/automatic
      model training already existed — it makes what already exists
      *visible* to someone who isn't going to read `kafkaf autonomy`/
      `kafkaf audit` CLI output or the docs to find it.
- [x] **Phase 17 — Real bugs from a real Windows desktop-app run, a real
      logo, and growing the own model from the app itself**: screenshots
      from the same live-testing user's actual `kafkaf-desktop` session
      surfaced several genuine problems at once:
      - The theme's "auto" mode requested geolocation **on first page
        load**, unprompted — a private-AI chat app asking for your location
        before you've done anything reads as alarming, not helpful. Fixed:
        first visit now resolves from `prefers-color-scheme` only; location
        is requested only once someone explicitly cycles the toggle into
        "auto" themselves.
      - Sending a message when Ollama isn't reachable showed `Couldn't get
        a reply from the model (). Is Ollama running...` — an **empty**
        `()`. Root cause: `httpx`'s timeout exception classes often
        stringify to `""` with no message, and `core/api.py`'s `/chat`
        handler used `f"...({exc})..."` directly. Fixed with a
        `str(exc) or type(exc).__name__` fallback so the detail is never
        blank. The screenshots also showed this hanging silently for a
        long time before erroring — `OllamaBrain` used one 120s timeout
        for everything; split into separate connect (5s) and read (120s)
        timeouts (`core/brains/ollama_brain.py`) so a genuinely-unreachable
        Ollama fails fast instead of looking exactly like a frozen app.
      - Checking "Council" without `KAFKAF_COUNCIL_BRAINS` configured
        produced a confusing dead-end error on send. `/status` now reports
        `council.configured`; the web GUI disables the checkbox upfront
        with an explanatory tooltip instead of letting you hit the error.
      - The Control Panel's 🎛️ button rendered as an empty placeholder box
        on the user's Windows machine — emoji glyph support isn't
        guaranteed even for moderately common emoji. Replaced with a
        hand-built inline SVG icon, which renders identically everywhere
        (no font dependency), and is the more robust choice for any future
        icon in this app.
      - The app icon set was a placeholder blue square with a white circle
        — shipped since the PWA phase and never revisited, and a fair
        target for "this looks generic." Designed a real logo (a flip-flop/
        sandal mark, matching כפכף's literal meaning) as an inline,
        theme-aware SVG for the header, and regenerated the full PWA/
        favicon PNG set from the same design via headless-browser
        rendering — no new dependency, no photorealistic-image-generation
        tool was available or needed for a clean vector mark.
      - Per explicit request, user-visible product-name surfaces
        (`<title>`, header, the desktop window title, the PWA manifest
        description) now show "KafKaf" only — the כפכף/כףכף wordmark was
        dropped from *those specific surfaces*. Project identity docs
        (README, CONTRIBUTING, persona flavor text, `pyproject.toml`) were
        deliberately left untouched — that's the project's name and
        character, not the in-app product-name display this request was
        about.
      - Biggest addition: **"our own model" is now teachable from the web
        GUI itself**, not only via the MCP server — the same complaint
        ("obviously our own model is the whole point") that motivated
        phase 6 originally. New `POST /enrichment/teach`, `POST
        /enrichment/distill`, `POST /enrichment/train` endpoints
        (`core/api.py`) reuse `enrichment/service.py`'s existing functions
        directly (`run_training_step` stays behind `asyncio.to_thread`,
        and a missing `torch` install now returns a clear 400 instead of
        a raw 500). The Control Panel gained a **Teach & grow** section:
        a topic+fact form for direct teaching, a button to have the
        default model explain a topic and capture that as training data,
        and a training-steps field + "Train now" button — all live,
        translated, refreshing the corpus/checkpoint numbers after every
        action.

      All of the above was live-verified end-to-end with Playwright against
      the real running server, including proving the geolocation fix by
      asserting no permission dialog fires on load, and proving the Grow
      panel actually works by teaching a fact through the UI and watching
      the corpus size go from 0 to 1 in the same panel.
- [x] **Phase 18 — No contradictions: a live autonomy switch, and a
      Playwright sweep that caught a real bug in the phase 17 work
      itself**: the user's demand, stated bluntly — "if I pick full
      autonomy, it must actually be full autonomy, with no more
      contradicting buttons." The concrete contradiction: the Skills
      checkbox (unlike Council, fixed in phase 17) didn't reflect whether
      skills were actually allowed at the current autonomy level —
      checking it at `observe` still produced a dead-end 400 on send. Fixed
      two ways at once: a new `POST /autonomy` endpoint changes
      `settings.autonomy_level` live, in-process, no restart (same
      singleton-mutation pattern the test suite already relied on via
      `monkeypatch`); and `refreshSkillsAvailability()` in `app.js` now
      disables *both* Council and Skills checkboxes together whenever the
      backend says either is unusable, re-checked immediately after any
      autonomy change from the Control Panel's new Observe/Assisted/
      Autonomous buttons. Scope stated honestly in both the UI hint and
      `docs/SETUP.md`: this affects the current process only — not a
      separately-running autopilot Docker container, and it doesn't
      survive a restart without also setting `KAFKAF_AUTONOMY_LEVEL`.

      Doing a full interactive-element sweep (every button, toggle, and
      dropdown, exercised end-to-end with Playwright against a real
      server) — the direct response to "keep improving every button, make
      sure everything works smoothly" — caught a real regression the unit
      tests had missed: `POST /enrichment/train` only caught
      `ModuleNotFoundError` (the "torch not installed" case). Training
      with too little taught data raises a real `ValueError` from
      `kafkaf/model/train.py` ("corpus too small for block_size"), which
      fell through the narrow catch straight into FastAPI's default
      handler — a raw, non-JSON 500, the exact bug class `/chat` was
      already fixed for in phase 15, reintroduced by the phase 17 work
      that added this endpoint. Fixed with a broad `except Exception`
      fallback (same pattern as `/chat` and `/enrichment/distill`), plus a
      regression test that raises a real `ValueError` and asserts a clean
      400 comes back. This is the second time in this project a
      Playwright-driven live sweep, not just unit tests, caught something
      real — the lesson from phase 14 held again: broader, more realistic
      verification finds gaps that narrower checks don't.
- [x] **Phase 19 — A third instance of the same bug class, always-visible
      persona/model explanations, three new skills, and a scoping decision
      on a much bigger ask**: real screenshots from the user's actual
      running `kafkaf-desktop` showed `brain: "own"` returning
      `Backend returned 500 with a non-JSON body`, while the default Ollama
      brain worked normally. Root cause, found by reading the code:
      `core/api.py`'s `/chat` handler resolves an explicit `brain`
      override in a try/except that only caught `ValueError`/
      `RuntimeError` — `get_brain("own")` lazy-imports `OwnModelBrain`,
      which imports `torch` (the optional `[train]` extra), and on a
      machine that only ran `pip install -e ".[dev]"` that raises
      `ModuleNotFoundError`, falling straight through into a raw,
      non-JSON 500. The third distinct instance of this exact bug class
      this session (`/chat`'s main handler in phase 15, `/enrichment/train`
      in phase 18) — each time a narrow except clause missed a real
      exception type. Fixed the same way: broaden the catch, with a
      message specific to this case (`brain: "own"` needs `pip install -e
      ".[train]"`), plus a regression test forcing `get_brain` to raise
      `ModuleNotFoundError` via monkeypatch.

      Also from the same message: "not clear what these dropdowns mean" —
      the `title`-attribute tooltips added in phase 17 were hover-only and
      not discoverable enough. Replaced with an always-visible selection-
      hint bar under the header (`#selection-hint` in `index.html`/
      `app.js`) that shows a plain-language description of the current
      persona *and* brain together, updating live as either changes, in
      both languages — no hover, no extra click.

      Shipped three new skills, all within the existing safe,
      no-code-execution skills framework (`core/skills/`): `system_info`
      (read-only OS/CPU/disk snapshot of the host KafKaf runs on, stdlib
      only), `journal` (a private timestamped notes log, same sandbox
      confinement as `files`), and `own_model_status` (surfaces
      `enrichment/service.py`'s `get_status()` conversationally, distinct
      from `memory_search`'s content search) — fourteen skills total now.

      **A scoping decision, recorded honestly**: the same message also
      asked for something much larger — an agent that "moves around the
      machine, organizes, protects, alerts, learns everything about
      everything" (comparing it to a commercial "Hermes Agent" product).
      Asked a clarifying multiple-choice question about the concrete
      technical scope (which directories, what "protect" means as an
      actual mechanism); the answer delegated the decision ("do what's
      needed... whatever you think") without supplying that scope. Given
      that code-execution/broad-system-access capability has already been
      proposed and blocked twice this session by the platform's own
      permission system as an unacceptable RCE surface — and that
      enthusiastic approval doesn't substitute for an actual technical
      spec — the decision was to build only the safe, in-sandbox tier
      (the three skills above) and explicitly not build broad host
      filesystem/process access or autonomous "protective" action this
      round. Documented in `docs/ROADMAP.md` (here) so it isn't silently
      dropped: if pursued later, it needs a concrete spec, not general
      enthusiasm, given the precedent.
- [x] **Phase 20 — Holding the line on unrestricted system access, then
      building the actual concrete request underneath it**: the user
      pressed repeatedly, across several messages, for unrestricted
      filesystem access for the autopilot loop ("the whole machine, no
      restrictions"), including the argument that human oversight
      ("we're always there, we choose the levels") made it safe. That
      argument doesn't hold against how the system is actually built —
      `autopilot` is specifically designed to run **unattended** (that's
      its entire purpose, and why `kafkaf-autopilot-ctl stop` exists as a
      real emergency stop), and skills execute within a ReAct turn without
      a per-call approval step. The request was declined, repeatedly and
      without the answer changing under pressure — consistent with the
      phase-19 decision, not a new one. The concrete risk, stated
      plainly: an unattended loop with existing outbound web skills
      (`web_search`/`web_fetch`) plus unrestricted local file read/write
      is a real data-exfiltration and data-destruction surface, not a
      hypothetical one.

      The breakthrough came when the user reframed the actual ask: *"like
      Claude Code, where you can choose"* — i.e., not unbounded access,
      but the same model this very session already uses: **one directory
      the user explicitly designates**, which could be broad (their whole
      home folder, if that's truly their deliberate choice) but is always
      a single, explicit, visible boundary rather than "everywhere, no
      boundary." That's a fundamentally different, buildable request —
      built it: `POST /skills/workspace` (`core/api.py`) changes
      `settings.skills_workspace_dir` live, in-process, the same
      runtime-mutation pattern as the phase-18 autonomy switch. The
      existing `core/skills/sandbox.py` path-traversal protection
      (`resolve_safe`) still applies unchanged — it never cared *where*
      the root was, only that nothing escapes it — so `files`,
      `document_search`, and `journal` become confined to wherever the
      user points them, moved live from the web GUI's new "Skills
      workspace directory" Control Panel section, with the current path
      always visible (`skills_workspace_dir` added to `GET /status`).
      This delivers real value ("help me with my actual files") within a
      boundary the user sets deliberately and can see, without the
      unattended-agent-with-unrestricted-disk-access risk profile that
      was correctly declined above.
- [x] **Phase 21 — Verifying a claimed bug instead of guessing, declining
      "skills that write skills," and five more real ones instead**: the
      user reported "sunset mode doesn't work." Rather than assume and
      rewrite the sunrise/sunset math, it was verified directly — computed
      Tel Aviv's sunset for a known date via the actual in-page function
      and cross-checked it against the real published sunset time (16:48
      UTC / 19:48 local, matching); the astronomical calculation was never
      the bug. The real gap: when geolocation is denied or unavailable,
      "auto" theme silently falls back to the OS preference with zero
      indication — indistinguishable from "broken" without opening
      developer tools. Fixed by making the fallback state visible: the
      theme button's tooltip now says outright whether it's using a real
      location-based sunset or the system-preference fallback (and, in the
      fallback case, that clicking would let it ask for location) — a
      transparency fix, not a math fix, verified with Playwright in both
      the granted- and denied-permission cases.

      The same message asked for a "skills generator" — a skill that
      would let the model write and load new skill code for itself,
      autonomously, for arbitrary future tasks. Declined, clearly: every
      existing skill is hand-written code that was reviewed before it
      ever executes; a generator means LLM-authored code executing with
      the same privileges as any other skill, with no review step in an
      unattended context — strictly worse than the plain code-execution
      capability already blocked twice this session, since it adds
      unbounded code *generation* on top of *execution*. Built five real,
      hand-written, reviewed skills instead, all following the same safe
      pattern as the other fourteen (no `eval`/`exec`, no subprocess):
      `password_generator` (Python's `secrets`, never a weak PRNG),
      `text_diff` (`difflib.unified_diff`), `hash_text` (md5/sha1/sha256),
      `random_pick` (dice rolls / picking from a list), and `text_stats`
      (word/character/sentence counts, reading time) — nineteen skills
      total. Separately: a screenshot sent as evidence turned out to be a
      screenshot of this Claude Code conversation itself, not of KafKaf —
      flagged honestly rather than analyzed as if it were the app.

## Deferred / future work

Surfaced by the phase 8 competitive research pass but deliberately not
built yet — named here so nothing is silently dropped:

- **A broader autonomous "system agent"** (moves around the host
  filesystem, organizes files, monitors/protects, alerts) — requested in
  phase 19, deliberately not built. Code-execution/broad-system-access
  capability has been proposed and blocked twice this session by the
  platform's own permission system as an unacceptable RCE surface given
  the unattended `autopilot` loop; this request is the same risk category
  at a larger scope. Needs a concrete technical spec before any of it is
  built — which directories, what "protect" does mechanically, what
  "alert" delivers and to where — not general approval alone.
- **Multi-user auth/RBAC** (local accounts or OAuth, per-user quotas) —
  needed only if KafKaf is ever meant for more than one trusted
  user/household over Tailscale; today's rate limiting and audit log are
  single-user-shaped, not multi-tenant-safe.
- **A dedicated native mobile app**, if the phase 11 PWA (installable,
  works over Tailscale, but still a web view under the hood) ever proves
  insufficient — push notifications and background sync are the concrete
  things a PWA can't do that a native app could.
- **A real observability sidecar** (e.g. self-hosted Langfuse or
  OpenTelemetry) for tracing/cost visibility across council-mode's
  multi-model fan-out, beyond what the audit log's summary rows capture.
- **A reverse-proxy gateway** (nginx/Caddy) in front of the backend for
  TLS termination and auth, if `rate_limit.py`'s in-memory single-process
  limiter ever stops being sufficient.
- **MCP-client integration** — letting KafKaf's own skills call out to
  *external* MCP servers (not just exposing KafKaf's own tools via its MCP
  server), reachable from the community's broader MCP tool ecosystem.
- **Sandboxed code execution** — flagged in phase 3, attempted and declined
  twice since: phase 9's subprocess-plus-resource-limits version, and phase
  10's bubblewrap/namespace-isolated version (blocked before it was even
  installed). Both attempts shared the same disqualifying property —
  reachable by the now-default-on autopilot loop with no human reviewing
  each call. Shipping this needs two things confirmed together, explicitly,
  not inferred from general "more autonomy" language: (1) real
  container/kernel-namespace isolation (no network access, read-only root,
  workspace-only writable — not just subprocess + rlimits), and (2) a gate
  that gives the *unattended autopilot loop* no path to it at all, ever —
  only interactive, human-initiated chat turns. Until both are true and
  explicitly signed off, this stays out.

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
