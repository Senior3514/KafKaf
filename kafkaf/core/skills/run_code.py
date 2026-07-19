"""Real Python code execution — the one skill in this project that can do
almost anything, which is exactly why it's requires_approval: it never
runs without a live human clicking approve first, no matter what
write_skills_mode is set to (see core/skills/loop.py, core/council.py's
resume_chat). It can never be scheduled or reached from the unattended
autopilot loop (core/skills/schedule.py, core/skills/registry.py).

Isolation is honest, not oversold: this is process-level sandboxing —
argument-list subprocess (never shell=True), cwd forced to the skills
workspace, a hard wall-clock timeout, and capped output. It is NOT
kernel/container isolation. In the Docker deployment this backend process
already runs inside a container, so a spawned subprocess inherits that
container's filesystem/network boundary "for free." Running as the
desktop app (no Docker) has no such boundary at all — per-action human
approval is the actual primary safety control there, not the sandbox.
Python only, deliberately — no general shell, to keep the execution
surface to one well-understood interpreter instead of every shell
metacharacter/builtin's combined risk.
"""

import asyncio
import subprocess
import sys

from kafkaf.core.config import settings
from kafkaf.core.skills import sandbox
from kafkaf.core.skills.base import Skill

MAX_OUTPUT_CHARS = 4000


def _truncate(text: str) -> str:
    if len(text) > MAX_OUTPUT_CHARS:
        return text[:MAX_OUTPUT_CHARS] + "... [truncated]"
    return text


class RunCodeSkill(Skill):
    name = "run_code"
    read_only = False
    requires_approval = True
    description = (
        "Run a piece of Python code and return its stdout/stderr. Always pauses for a "
        "live human approval click before it runs — never executes unattended. "
        "Process-level sandboxing only (workspace-jailed working directory, a wall-clock "
        "timeout, capped output) — not full container/kernel isolation; no network "
        "blocking is guaranteed. Usage: the Python source code to run, as-is."
    )

    async def run(self, arg: str) -> str:
        code = arg
        if not code.strip():
            return "error: no code given"

        try:
            result = await asyncio.to_thread(
                subprocess.run,
                [sys.executable, "-c", code],
                cwd=str(sandbox.workspace_root()),
                capture_output=True,
                timeout=settings.run_code_timeout_seconds,
                text=True,
            )
        except subprocess.TimeoutExpired:
            return f"error: code exceeded the {settings.run_code_timeout_seconds}s timeout and was killed"
        except OSError as exc:
            return f"error: could not run code: {exc}"

        parts = [f"exit={result.returncode}"]
        if result.stdout:
            parts.append(f"stdout:\n{_truncate(result.stdout)}")
        if result.stderr:
            parts.append(f"stderr:\n{_truncate(result.stderr)}")
        return "\n".join(parts) if len(parts) > 1 else f"exit={result.returncode} (no output)"
