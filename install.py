#!/usr/bin/env python3
"""The one KafKaf install command — works the same on Linux, macOS, and Windows.

    python install.py                                     # web GUI on :8420, autonomy=autonomous (autopilot ON)
    TS_AUTHKEY=tskey-... python install.py --tailscale     # private tailnet only, no public port
    python install.py --autonomy assisted                  # skills available, no unattended growth loop
    python install.py --autonomy observe                   # chat only, no tools, no autopilot

Flags combine: `python install.py --tailscale --autonomy assisted` gets you both.

Brings up the full backend + web GUI (Docker: Ollama + KafKaf), pulls the
default local model, and prints next steps for the CLI and desktop app.
Requires Docker (with the Compose plugin) — https://docs.docker.com/get-docker/

--tailscale gets you a real "access layer": the backend is reachable ONLY
over your private Tailscale network (no port published to the public
internet at all). See docs/SETUP.md for how to get a TS_AUTHKEY.

--autonomy is a single, legible dial for how much KafKaf can do on its
own — see docs/SETUP.md#autonomy-levels for the full table. Defaults to
'autonomous': skills (tools) are available, and autopilot (the unattended
teach-and-train curriculum loop) runs by default — a real emergency stop
(`kafkaf-autopilot-ctl stop`) is always available if you want it paused.
`--no-autopilot` is a narrower override: stay at --autonomy autonomous but
skip only the autopilot container. See docs/GUIDE.md for autopilot pacing/
cost tuning (defaults are conservative, not "as fast as possible").
"""

import argparse
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
DEPLOY_DIR = PROJECT_ROOT / "deploy"
BASE_COMPOSE = DEPLOY_DIR / "docker-compose.yml"
LOCAL_OVERLAY = DEPLOY_DIR / "docker-compose.local.yml"
TAILSCALE_OVERLAY = DEPLOY_DIR / "docker-compose.tailscale.yml"
AUTOPILOT_OVERLAY = DEPLOY_DIR / "docker-compose.autopilot.yml"
MODE_MARKER = DEPLOY_DIR / ".compose-mode"
# Matches deploy/install.sh's fallback and honors the same override so
# setting KAFKAF_OLLAMA_MODEL before running this actually pulls the model
# the backend will request, instead of silently pulling a different one.
DEFAULT_MODEL = os.environ.get("KAFKAF_OLLAMA_MODEL", "qwen3:4b")


def run(*args: str) -> None:
    subprocess.run(args, check=True)


def compose_files(tailscale: bool, autopilot: bool) -> list[str]:
    overlay = TAILSCALE_OVERLAY if tailscale else LOCAL_OVERLAY
    files = ["-f", str(BASE_COMPOSE), "-f", str(overlay)]
    if autopilot:
        files += ["-f", str(AUTOPILOT_OVERLAY)]
    return files


def docker_compose(files: list[str], *args: str) -> None:
    run("docker", "compose", *files, *args)


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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tailscale",
        action="store_true",
        help="Reachable only over your private tailnet — no public port published.",
    )
    parser.add_argument(
        "--autonomy",
        choices=["observe", "assisted", "autonomous"],
        default="autonomous",
        help="How much KafKaf can do on its own: 'observe' (chat only), "
        "'assisted' (skills available, no unattended loop), 'autonomous' "
        "(skills + autopilot running by default — the default). "
        "See docs/SETUP.md#autonomy-levels.",
    )
    parser.add_argument(
        "--no-autopilot",
        action="store_true",
        help="Narrower override: keep --autonomy autonomous's skills enabled, "
        "but skip only the autopilot container (stop/resume a running one "
        "anytime with `kafkaf-autopilot-ctl` instead).",
    )
    args = parser.parse_args()
    autopilot = args.autonomy == "autonomous" and not args.no_autopilot
    # Read by deploy/docker-compose.yml (${KAFKAF_AUTONOMY_LEVEL:-autonomous})
    # — this is a CLI flag, not something the user is expected to export
    # themselves, so set it here for the docker compose subprocess to inherit.
    os.environ["KAFKAF_AUTONOMY_LEVEL"] = args.autonomy

    if shutil.which("docker") is None:
        print(
            "Docker is required. Install it first: https://docs.docker.com/get-docker/",
            file=sys.stderr,
        )
        raise SystemExit(1)

    if args.tailscale and not os.environ.get("TS_AUTHKEY"):
        print(
            "TS_AUTHKEY is not set. Get one from https://tailscale.com/kb/1085/auth-keys "
            "and run:\n  TS_AUTHKEY=tskey-... python install.py --tailscale",
            file=sys.stderr,
        )
        raise SystemExit(1)

    files = compose_files(args.tailscale, autopilot)

    print("==> Starting KafKaf (Ollama + backend + web GUI)...")
    docker_compose(files, "up", "-d", "--build")

    print("==> Waiting for Ollama to be ready...")
    wait_for_ollama()

    print(f"==> Pulling local model: {DEFAULT_MODEL}")
    docker_compose(files, "exec", "-T", "ollama", "ollama", "pull", DEFAULT_MODEL)

    MODE_MARKER.write_text(
        f"{'tailscale' if args.tailscale else 'local'}\n"
        f"{'autopilot' if autopilot else ''}\n"
    )

    print()
    print("KafKaf is up.")
    print(f"  Autonomy:   {args.autonomy}")
    if args.tailscale:
        print("  Not published publicly — reachable only on your tailnet.")
        print("  Run `tailscale status` to find it, or check the admin console;")
        print("  it should appear as an HTTPS URL like https://kafkaf.<your-tailnet>.ts.net")
    else:
        print("  Web GUI:    http://localhost:8420")
        print("  Health:     http://localhost:8420/health")
    if autopilot:
        print("  Autopilot:  running — `docker compose -f deploy/docker-compose.yml logs -f autopilot`")
        print("              stop anytime: `docker compose -f deploy/docker-compose.yml exec autopilot kafkaf-autopilot-ctl stop`")
    print()
    print("Optional next steps:")
    print('  CLI:        pip install -e ".[dev]"   then   kafkaf chat "hello"')
    print('  Desktop:    pip install -e ".[desktop]"   then   kafkaf-desktop')
    print(
        '  Enrichment: pip install -e ".[mcp,train]"   then   kafkaf-mcp   (see docs/SETUP.md)'
    )
    print("  Update:     ./deploy/update.sh   (picks up this same mode automatically)")


if __name__ == "__main__":
    main()
