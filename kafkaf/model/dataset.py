import torch

from kafkaf.model import tokenizer

_EXAMPLE_SEPARATOR = "\x00"


def examples_to_byte_stream(examples: list[dict[str, str]]) -> list[int]:
    """Concatenate prompt/completion pairs into one byte stream, separated by NUL bytes
    so the model can learn to respect example boundaries."""
    text = _EXAMPLE_SEPARATOR.join(
        f"{example['prompt']}\n{example['completion']}" for example in examples
    )
    return tokenizer.encode(text + _EXAMPLE_SEPARATOR)


def get_batch(
    data: list[int], block_size: int, batch_size: int, device: str = "cpu"
) -> tuple[torch.Tensor, torch.Tensor]:
    if len(data) <= block_size:
        raise ValueError("Not enough data for a single block — teach a few more examples first.")

    data_tensor = torch.tensor(data, dtype=torch.long)
    max_start = len(data_tensor) - block_size - 1
    starts = torch.randint(0, max_start, (batch_size,))
    x = torch.stack([data_tensor[i : i + block_size] for i in starts])
    y = torch.stack([data_tensor[i + 1 : i + block_size + 1] for i in starts])
    return x.to(device), y.to(device)
