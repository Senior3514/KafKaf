# KafKaf (כףכף)

Your own AI team — private, local, free, and always learning.

KafKaf is a free, open-source, self-hosted AI agent platform. It runs local
open-source language models by default (nothing leaves your machine), can
fan a query out across several models in parallel ("council of brains"),
and ships with personas, skills, and persistent memory — plus its own
from-scratch-trained model that keeps growing as you teach it (see
`docs/ROADMAP.md`). Every interface — web GUI, desktop app, CLI/terminal —
is a thin client over the same core API.

This is not a claim of AGI/ASI — no one has built that, and it isn't where
this leads no matter how long it grows. See `docs/ROADMAP.md`'s vision
section for what the actual, honest, worthwhile goal is. It's a practical
platform for running your own AI, on your own hardware, for free.

**New here? `docs/GUIDE.md` is the single start-to-finish walkthrough** —
VPS install, every interface, growing your own model, all in one place.
This README is the short version.

## Quick start — one command, every OS

Requires [Docker](https://docs.docker.com/get-docker/) (Linux, macOS, and
Windows via Docker Desktop all work identically):

```
python install.py
```

This brings up Ollama + the KafKaf backend and pulls the default local
model. Then open **http://localhost:8420** in a browser for the web GUI —
that's it, no separate frontend build step.

## Every interface

- **Web GUI** — `http://localhost:8420` once the backend is running (see
  above). Mobile-first, works in any browser.
- **CLI / terminal**:
  ```
  pip install -e .
  kafkaf chat "Hey KafKaf, who are you?"   # one-shot
  kafkaf repl                               # interactive terminal session
  ```
- **Desktop app** (native window, same GUI, packaged into a single exe per
  OS via CI — see `.github/workflows/build-desktop.yml` and
  `docs/SETUP.md`):
  ```
  pip install -e ".[desktop]"
  kafkaf-desktop
  ```
- **API directly**:
  ```
  curl -X POST http://localhost:8420/chat \
    -H 'Content-Type: application/json' \
    -d '{"message": "hello"}'
  ```
- **MCP server** (teach/train KafKaf's own model from Claude Desktop/Code)
  — see `docs/SETUP.md`.

## Running on a VPS, and keeping it updated

`python install.py` (or `deploy/install.sh`) works the same on a VPS as
locally. To pull the latest code from the repo and rebuild/restart:

```
./deploy/update.sh
```

By default the web GUI/API is published on the VPS's public IP at `:8420`.
For a real private access layer instead — reachable only from your own
devices, no public port at all — install with
[Tailscale](https://tailscale.com):

```
TS_AUTHKEY=tskey-... python install.py --tailscale
```

See `docs/SETUP.md#tailscale-access-layer` for how to get a key.

Autopilot (unattended teach-and-train) runs **by default** — KafKaf keeps
learning on its own out of the box, with a real emergency stop always
available (`kafkaf-autopilot-ctl stop`). Want less autonomy? One dial,
`--autonomy {observe,assisted,autonomous}` (combines with `--tailscale`),
controls how much KafKaf can do without a human approving each step — see
`docs/SETUP.md#autonomy-levels`.

## Development

```
pip install -e ".[dev]"
pytest
```

Run the backend without Docker (needs a local Ollama running on
`localhost:11434`):

```
kafkaf-server
```

Contributing? See `CONTRIBUTING.md` for this codebase's conventions
(storage pattern, brain interface, skill shape, dependency philosophy)
before opening a PR.

## Project layout

See `docs/ARCHITECTURE.md` for the full picture. In short:

- `kafkaf/core` — the orchestrator: brains (model adapters), personas,
  memory, enrichment, the API (which also serves the web GUI).
- `kafkaf/model` — our own from-scratch-trained model.
- `kafkaf/clients` — CLI, desktop, and web clients — all thin, all over the
  core API.
- `kafkaf/mcp` — the local MCP server for teaching/training the own model.
- `deploy` — Docker Compose stack, VPS install/update scripts.

## Roadmap

See `docs/ROADMAP.md` — this is a "grow it over time" project, built in
phases, each shipping something runnable.

## License

MIT — see `LICENSE`. Contributions welcome.
