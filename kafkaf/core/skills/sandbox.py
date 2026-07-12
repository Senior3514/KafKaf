"""The sandboxed workspace directory shared by every skill that touches the
filesystem (`files`, `document_search`) — one place that owns the
path-safety check so it's never re-implemented (and potentially
re-broken) per skill."""

from pathlib import Path

from kafkaf.core.config import settings


def workspace_root() -> Path:
    root = Path(settings.skills_workspace_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def resolve_safe(relative_path: str) -> Path:
    root = workspace_root()
    candidate = (root / relative_path).resolve()
    if candidate != root and root not in candidate.parents:
        raise ValueError("path escapes the sandboxed workspace directory")
    return candidate
