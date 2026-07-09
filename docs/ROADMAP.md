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
- [ ] **Phase 6 — Own-model training track**: a small transformer we design
      and pretrain ourselves (not a repackaged checkpoint) on a curated
      corpus, plus a continual learning/fine-tuning loop so it keeps
      improving as it's used. Folded into the council as just another brain
      once it reaches usable quality.
- [ ] **Phase 7 — Deployment automation**: polish `deploy/install.sh` and
      `docker-compose.yml` into a true one-command VPS setup; finish
      setup/contribution docs for the public release.

## Notes on scope

- KafKaf does not claim to be AGI/ASI. It's an honest, practical, private,
  free AI agent platform — see the top of the main `README.md`.
- Model sizes in phases 2 and 6 assume no dedicated GPU is available yet.
  Once real hardware is confirmed, `deploy/docker-compose.yml`'s
  `KAFKAF_OLLAMA_MODEL` and the training config in phase 6 should be scaled
  up accordingly.
