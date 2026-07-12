from pathlib import Path

from kafkaf.core.config import settings
from kafkaf.core.skills.base import Skill

MAX_READ_CHARS = 4000
MAX_WRITE_CHARS = 20000


def _workspace_root() -> Path:
    root = Path(settings.skills_workspace_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _resolve_safe(relative_path: str) -> Path:
    root = _workspace_root()
    candidate = (root / relative_path).resolve()
    if candidate != root and root not in candidate.parents:
        raise ValueError("path escapes the sandboxed workspace directory")
    return candidate


class FilesSkill(Skill):
    name = "files"
    description = (
        "Read/write/list files in a sandboxed workspace directory. Usage: "
        "'list', 'read <path>', or 'write <path>\\n<content>'."
    )

    async def run(self, arg: str) -> str:
        arg = arg.strip()

        if arg in ("", "list"):
            root = _workspace_root()
            names = sorted(p.name for p in root.iterdir() if p.is_file())
            return "\n".join(names) if names else "(workspace is empty)"

        if arg.startswith("read "):
            try:
                path = _resolve_safe(arg[len("read ") :].strip())
            except ValueError as exc:
                return f"error: {exc}"
            if not path.exists():
                return f"error: no such file: {path.name}"
            content = path.read_text(encoding="utf-8", errors="replace")
            if len(content) > MAX_READ_CHARS:
                content = content[:MAX_READ_CHARS] + "... [truncated]"
            return content

        if arg.startswith("write "):
            rest = arg[len("write ") :]
            if "\n" not in rest:
                return "error: expected 'write <path>\\n<content>'"
            rel_path, content = rest.split("\n", 1)
            try:
                path = _resolve_safe(rel_path.strip())
            except ValueError as exc:
                return f"error: {exc}"
            content = content[:MAX_WRITE_CHARS]
            path.write_text(content, encoding="utf-8")
            return f"wrote {len(content)} chars to {path.name}"

        return "error: unrecognized command — use 'list', 'read <path>', or 'write <path>\\n<content>'"
