# Contributing to KafKaf

KafKaf (כףכף) is a free, open-source, self-hosted AI platform. Contributions
are welcome — this document covers how to get set up and what this
codebase's existing conventions are, so a PR fits in without a big
back-and-forth. See `CODE_OF_CONDUCT.md` for how project spaces are run.

## Getting set up

```bash
git clone https://github.com/Senior3514/KafKaf.git
cd KafKaf
pip install -e ".[dev]"
pytest
```

No Ollama or Docker needed to run the test suite — it uses fake/stub
brains throughout (see any `FakeBrain`/`FixedBrain` in `tests/`), so it's
fast and fully offline. `pip install -e ".[train]"` additionally pulls in
`torch` if you're touching `kafkaf/model/` or `kafkaf/core/enrichment/`;
`pip install -e ".[mcp]"` for `kafkaf/mcp/`.

To run the backend locally against a real model, you need
[Ollama](https://ollama.com/download) running (`ollama serve`, then
`ollama pull qwen3:4b` or whichever model you're testing against), then
`kafkaf-server`. See `docs/SETUP.md` for the full manual-dev-setup section.

## Before opening a PR

- `pytest` passes.
- If you touched `deploy/docker-compose*.yml`, validate the merge:
  `docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.local.yml config`.
- If you touched `install.py` or `deploy/install.sh`, check them for
  syntax at minimum (`python3 -c "import ast; ast.parse(open('install.py').read())"`,
  `bash -n deploy/install.sh`) — neither has a way to be exercised
  end-to-end without a real Docker daemon and internet access.

## Conventions this codebase actually follows

Read a few existing files in the area you're touching before writing new
code — these patterns are consistent on purpose, not incidental:

- **One storage pattern.** Every SQLite-backed store (`core/memory/store.py`,
  `core/enrichment/store.py`, `core/audit/store.py`, `core/skills/store.py`)
  is a module-level `_SCHEMA` string, a `@contextmanager _connect()` using
  `kafkaf.core.db.connect(settings.db_path)`, and plain functions — no ORM,
  no classes. Match it rather than introducing a new pattern.
- **Brains are provider-agnostic.** Every model integration implements
  `kafkaf/core/brains/base.py`'s `Brain` (a `name` and one async
  `generate(messages) -> str`). Plain `httpx` REST calls, not provider
  SDKs — see `openai_brain.py`/`anthropic_brain.py`/`gemini_brain.py` for
  the shape. New teacher/chat model support goes through
  `core/brains/registry.py`, not bespoke calling code elsewhere.
- **Skills take one string argument, return one string.** Not multi-field
  JSON — small local models format `ACTION: <tool>: <arg>` far more
  reliably than structured function-calling. See `core/skills/base.py` and
  any existing skill for the shape. Filesystem-touching skills go through
  `core/skills/sandbox.py`'s `workspace_root()`/`resolve_safe()` — never
  reinvent path-traversal checking.
- **Minimal dependencies, hand-rolled over pulled-in.** `calculator.py` is
  an `ast`-based safe evaluator, not `eval`. `document_search.py` is
  keyword/paragraph-chunk scoring, not a vector DB. `rate_limit.py` is an
  in-memory fixed-window counter, not Redis. If a few dozen lines of
  stdlib does the job, prefer that over a new dependency — and if you do
  need one, say why in the PR description.
- **Optional extras (`torch`, `mcp`, `pywebview`) stay lazily imported.**
  `enrichment/service.py`'s `train_step` import and `brains/registry.py`'s
  `OwnModelBrain` import are both local (inside the function that actually
  needs them), specifically so `pip install -e ".[dev]"` alone is enough
  to run `kafkaf-server` and every brain except `"own"`. A module-level
  `import torch` anywhere reachable from `core/api.py` breaks that
  guarantee — this exact bug shipped once (docs/ROADMAP.md phase 14) and
  is now covered by a regression test that actually blocks the import.
- **No silent capability changes.** Anything that changes what KafKaf can
  do without a human reviewing each step (new skills, autopilot behavior,
  default autonomy) goes through `core/autonomy.py`'s tiers and gets
  called out explicitly in `docs/ROADMAP.md` — including things that were
  *considered and declined*, not just what shipped. See the Phase 9/10
  entries for the tone: declined capabilities are documented with the
  actual reasoning and the bar for revisiting them, not silently dropped.
- **Comments explain why, not what.** Default to none. Add one only for a
  non-obvious constraint, a subtle invariant, or a workaround for a
  specific bug — never to restate what a well-named function already says.
- **Honesty about capability.** This project is explicit that it is not,
  and will not become, AGI/ASI (see `docs/ROADMAP.md`'s vision section,
  with citations) — a small model taught more facts for longer is not on
  a path to general intelligence. Docs and commit messages should stay
  calibrated to what was actually built and verified, not what would be
  impressive if true.

## Security-sensitive changes

Anything that expands what an automated part of the system (autopilot, a
skill) can do to the host — filesystem access beyond the sandboxed
workspace, network access, process execution, new inherited credentials —
needs an explicit, specific description of the new capability and its
blast radius in the PR description. "More autonomy" or "more permissions"
in an issue/request is not sufficient justification on its own; see
`docs/ROADMAP.md`'s Phase 9/10 entries for two concrete examples of
capability requests that were built and then declined for exactly this
reason. When in doubt, open an issue describing the tradeoff before
writing code.

## Where things are documented

- `docs/ARCHITECTURE.md` — system map, one section per subsystem.
- `docs/ROADMAP.md` — what's built, what's deferred and why, phase by
  phase (a real changelog-with-reasoning, not just a TODO list).
- `docs/SETUP.md` / `docs/GUIDE.md` — user-facing install/usage docs;
  update these if your change affects install flow, config, or an
  interface (CLI/API/web GUI/MCP).

## License

MIT — see `LICENSE`. By contributing, you agree your contribution is
licensed under the same terms.
