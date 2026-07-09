# KafKaf (כףכף)

Your own AI team — private, local, free, and always learning.

KafKaf is a free, open-source, self-hosted AI agent platform. It runs local
open-source language models by default (nothing leaves your machine), can
fan a query out across several models in parallel ("council of brains"),
and ships with personas, skills, and persistent memory. Every interface —
CLI, terminal UI, desktop app, and a mobile-first web app — is a thin client
over the same core API.

This is not a claim of AGI/ASI — no one has built that. It's a practical,
honest platform for running your own AI, on your own hardware, for free,
and growing it over time (including a from-scratch-trained small model —
see `docs/ROADMAP.md`).

## Quick start

Requires [Docker](https://docs.docker.com/engine/install/).

```
./deploy/install.sh
```

This starts a local Ollama instance plus the KafKaf backend, and pulls the
default model. Then talk to it:

```
pip install -e .
kafkaf chat "Hey KafKaf, who are you?"
```

Or hit the API directly:

```
curl -X POST http://localhost:8420/chat \
  -H 'Content-Type: application/json' \
  -d '{"message": "hello"}'
```

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

## Project layout

See `docs/ARCHITECTURE.md` for the full picture. In short:

- `kafkaf/core` — the orchestrator: brains (model adapters), personas,
  memory, the API.
- `kafkaf/clients` — CLI, and (coming soon) terminal UI, desktop, and web
  clients — all thin, all over the core API.
- `deploy` — Docker Compose stack and VPS install script.

## Roadmap

See `docs/ROADMAP.md` — this is a "grow it over time" project, built in
phases, each shipping something runnable.

## License

MIT — see `LICENSE`. Contributions welcome.
