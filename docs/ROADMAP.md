# Roadmap

KafKaf is built in phases; each one ships something runnable. No phase
depends on a big-bang release — "grow it over time."

- [x] **Phase 1 — Scaffolding**: repo layout, license, docs, base tooling.
- [x] **Phase 2 — Core loop end-to-end**: backend API + one local model
      (Ollama) + one persona + basic memory + thin CLI client. Works fully
      locally, zero API keys required.
- [ ] **Phase 3 — Council + skills**: parallel multi-brain routing and
      synthesis, tool-use skills plugin system, multiple personas, optional
      API-model brains.
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
- [x] **Phase 6 — Own-model training track (initial slice)**: a small
      transformer we design and pretrain ourselves (`kafkaf/model/` —
      byte-level nanoGPT-style GPT, no downloaded checkpoint), a corpus +
      continual-training loop (`kafkaf/core/enrichment/`), teacher brains for
      OpenAI/Anthropic/Gemini/Ollama (`kafkaf/core/brains/`), and a local MCP
      server (`kafkaf/mcp/server.py`, stdio, single-user) exposing
      `teach_fact`, `distill_from_teacher`, `train_step`, `status`, and
      `chat_with_own_model` — usable today from Claude Desktop/Code. Not yet
      done: wiring `OwnModelBrain` into the council's default routing
      (deliberately deferred until quality warrants it), scheduled/unattended
      training runs, and a subword tokenizer upgrade.
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
