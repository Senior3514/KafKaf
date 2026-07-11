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
- [ ] **Phase 4 — Web (mobile-first) + terminal UI**: both consume the same
      core API; web is a responsive installable PWA, the TUI is a
      terminal-native alternative to the CLI for interactive sessions.
- [ ] **Phase 5 — Desktop packaging**: Tauri wrapper around the web client,
      producing installable Windows/macOS/Linux binaries.
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
- [ ] **Phase 7 — Deployment automation**: polish `deploy/install.sh` and
      `docker-compose.yml` into a true one-command VPS setup; finish
      setup/contribution docs for the public release.

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
