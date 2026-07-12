"""Zero-dependency byte-level tokenizer. Every byte is a token (vocab_size=256)."""


def encode(text: str) -> list[int]:
    return list(text.encode("utf-8"))


def decode(ids: list[int]) -> str:
    return bytes(ids).decode("utf-8", errors="replace")
