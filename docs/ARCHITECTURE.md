# Architecture

One core backend API; every interface (CLI, terminal UI, desktop, web) is a
thin client over it. This avoids duplicating orchestration logic per client.

```
kafkaf/
  core/
    brains/       # adapters: local models (Ollama) + optional API models
    council.py    # routes a chat turn to a brain (grows into multi-brain
                   # parallel routing + synthesis as more brains are added)
    personas/     # persona configs (system prompt, name)
    memory/       # persistent per-session conversation history (SQLite)
    api.py        # FastAPI app: /health, /chat
    server.py     # uvicorn entrypoint (`kafkaf-server`)
  clients/
    cli/          # thin CLI (typer) — talks to core/api.py over HTTP
    # tui/, desktop/, web/ — planned, see ROADMAP.md
  model/          # planned: our own from-scratch-trained model, see ROADMAP.md
deploy/
  Dockerfile
  docker-compose.yml   # ollama + backend, for local/VPS use
  install.sh            # one-shot setup script
docs/
tests/
```

## Local model runtime

[Ollama](https://ollama.com) is the default local inference engine — simplest
to self-host, and it serves quantized open models (Llama 3, Qwen2.5, Phi-3,
Gemma2, ...). Pick the model size to match available RAM/VRAM; the default in
`deploy/docker-compose.yml` is a small model that runs reasonably on CPU.
API-backed models (Claude, GPT, etc., via a user-supplied key) are meant to be
opt-in extra brains later — never required for KafKaf to work.

## Council / multi-brain pattern

`core/council.py` is the single seam where a chat turn is resolved. Today it
routes to one configured brain. The intended growth path (see
`docs/ROADMAP.md`, phase 3) is: fan a query out to N configured brains in
parallel, then synthesize/rank the answers — an honest "ensemble of models"
version of "multiple brains," not a claim of general intelligence.

## Memory

`core/memory/store.py` is a small SQLite-backed conversation log, keyed by
`session_id`. It's intentionally simple for phase 2; a vector-store-backed
long-term memory is a natural phase-3+ upgrade once retrieval-augmented
recall is needed.

## Privacy

Nothing leaves the machine running KafKaf unless a persona/query explicitly
opts into an API-backed brain. The default docker-compose stack talks only
to the local Ollama container.
