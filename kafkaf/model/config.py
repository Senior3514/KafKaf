from dataclasses import dataclass


@dataclass
class GPTConfig:
    vocab_size: int
    block_size: int
    n_layer: int
    n_head: int
    n_embd: int
    dropout: float = 0.1


# Byte-level vocab (256) — no tokenizer dependency, keeps the vocab trivially small.
# CPU-friendly starting point: ~1-2M params.
TINY = GPTConfig(vocab_size=256, block_size=128, n_layer=4, n_head=4, n_embd=128, dropout=0.1)

# Same architecture, scaled up for when real GPU hardware is available.
SMALL = GPTConfig(vocab_size=256, block_size=512, n_layer=12, n_head=12, n_embd=384, dropout=0.1)

PRESETS = {"tiny": TINY, "small": SMALL}


def get_preset(name: str) -> GPTConfig:
    if name not in PRESETS:
        raise ValueError(f"Unknown model preset: {name!r}. Known presets: {sorted(PRESETS)}")
    return PRESETS[name]
