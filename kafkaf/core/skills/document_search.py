"""A small, dependency-free "RAG-lite" skill: keyword search over the
content of files already dropped into the sandboxed workspace (via the
`files` skill), not just their names. No vector DB or embeddings model —
paragraph chunking + keyword-overlap scoring, the same philosophy as
`memory_search`'s plain keyword matching and `calculator`'s hand-rolled
safe eval: minimal dependencies, good enough to be genuinely useful."""

import re

from kafkaf.core.skills.base import Skill
from kafkaf.core.skills.sandbox import workspace_root

CHUNK_CHARS = 500
MAX_RESULTS = 5
SUPPORTED_SUFFIXES = {".txt", ".md", ".rst", ".csv", ".json", ".log"}

_WORD_RE = re.compile(r"\w+")


def _chunks(text: str) -> list[str]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks = []
    for paragraph in paragraphs:
        for i in range(0, len(paragraph), CHUNK_CHARS):
            chunk = paragraph[i : i + CHUNK_CHARS].strip()
            if chunk:
                chunks.append(chunk)
    return chunks


def _score(chunk: str, terms: list[str]) -> int:
    lowered = chunk.lower()
    return sum(lowered.count(term) for term in terms)


class DocumentSearchSkill(Skill):
    name = "document_search"
    description = (
        "Search the text CONTENT of files in the sandboxed workspace by keyword "
        "(not just filenames) — a simple local knowledge-base search. Usage: "
        "'<query>'. Only .txt/.md/.rst/.csv/.json/.log files are searched; add "
        "files first with the 'files' skill's write command."
    )

    async def run(self, arg: str) -> str:
        query = arg.strip()
        if not query:
            return "error: empty query"

        terms = [t.lower() for t in _WORD_RE.findall(query)]
        if not terms:
            return "error: no searchable terms in query"

        root = workspace_root()
        scored: list[tuple[int, str, str]] = []
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in SUPPORTED_SUFFIXES:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            for chunk in _chunks(text):
                score = _score(chunk, terms)
                if score > 0:
                    scored.append((score, path.name, chunk))

        if not scored:
            return "no matching content found in the workspace"

        scored.sort(key=lambda item: item[0], reverse=True)
        return "\n\n".join(
            f"[{name}] (relevance {score}): {chunk}" for score, name, chunk in scored[:MAX_RESULTS]
        )
