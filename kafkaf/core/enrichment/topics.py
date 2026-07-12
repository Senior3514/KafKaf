from pathlib import Path

# A small, honest starter curriculum — customize via a topics file (one topic
# per line) rather than expecting this list alone to make the model broadly
# capable. It won't; see docs/ROADMAP.md's vision section for why.
DEFAULT_TOPICS = [
    "what KafKaf is: a free, private, self-hosted AI platform",
    "why KafKaf is not, and cannot become, AGI or ASI",
    "what makes a good, concise, honest answer to a question",
    "how to explain a technical concept simply",
    "the difference between a fact and an opinion",
    "how to politely say 'I don't know' instead of guessing",
    "what privacy means for personal data",
    "how to summarize a long piece of text",
    "the basics of how a transformer language model works",
    "what continual learning means for a small model",
    "how to break a big task into smaller steps",
    "common courtesy phrases in conversation",
]


def load_topics(path: str | None) -> list[str]:
    """Load a custom newline-separated topics file, or fall back to the
    built-in default curriculum. Blank lines and '#' comments are ignored."""
    if path:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
        topics = [line.strip() for line in lines if line.strip() and not line.strip().startswith("#")]
        if topics:
            return topics
    return list(DEFAULT_TOPICS)
