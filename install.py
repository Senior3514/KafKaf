#!/usr/bin/env python3
"""The one KafKaf install command — works the same on Linux, macOS, and Windows.

    python install.py

Brings up the full backend + web GUI (Docker: Ollama + KafKaf), pulls the
default local model, and prints next steps for the CLI and desktop app.
Requires Docker (with the Compose plugin) — https://docs.docker.com/get-docker/
"""

import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
COMPOSE_FILE = PROJECT_ROOT / "deploy" / "docker-compose.yml"
DEFAULT_MODEL = "qwen2.5:3b"


def run(*args: str) -> None:
    subprocess.run(args, check=True)


def docker_compose(*args: str) -> None:
    run("docker", "compose", "-f", str(COMPOSE_FILE), *args)


def wait_for_ollama(timeout_seconds: int = 120) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=2):
                return
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            time.sleep(2)
    raise RuntimeError("Ollama did not become ready in time.")


def main() -> None:
    if shutil.which("docker") is None:
        print(
            "Docker is required. Install it first: https://docs.docker.com/get-docker/",
            file=sys.stderr,
        )
        raise SystemExit(1)

    print("==> Starting KafKaf (Ollama + backend + web GUI)...")
    docker_compose("up", "-d", "--build")

    print("==> Waiting for Ollama to be ready...")
    wait_for_ollama()

    print(f"==> Pulling local model: {DEFAULT_MODEL}")
    docker_compose("exec", "-T", "ollama", "ollama", "pull", DEFAULT_MODEL)

    print()
    print("KafKaf is up.")
    print("  Web GUI:    http://localhost:8420")
    print("  Health:     http://localhost:8420/health")
    print()
    print("Optional next steps:")
    print('  CLI:        pip install -e ".[dev]"   then   kafkaf chat "hello"')
    print('  Desktop:    pip install -e ".[desktop]"   then   kafkaf-desktop')
    print(
        '  Enrichment: pip install -e ".[mcp,train]"   then   kafkaf-mcp   (see docs/SETUP.md)'
    )


if __name__ == "__main__":
    main()
