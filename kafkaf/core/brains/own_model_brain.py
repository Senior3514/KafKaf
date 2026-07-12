import asyncio
from pathlib import Path

import torch

from kafkaf.core.brains.base import Brain
from kafkaf.core.config import settings
from kafkaf.model import tokenizer
from kafkaf.model.config import GPTConfig
from kafkaf.model.gpt import GPT


class OwnModelBrain(Brain):
    """Our own from-scratch-trained model — quality grows as it's taught and trained.

    Runs inference via asyncio.to_thread since torch inference is synchronous
    and CPU-bound, and must not block the event loop.
    """

    name = "kafkaf-own"

    def __init__(self, checkpoint_path: str | None = None):
        self.checkpoint_path = checkpoint_path or settings.own_model_checkpoint_path
        self._model: GPT | None = None
        self._config: GPTConfig | None = None

    def _load(self) -> GPT:
        if self._model is not None:
            return self._model

        path = Path(self.checkpoint_path)
        if not path.exists():
            raise RuntimeError(
                f"No trained checkpoint at {self.checkpoint_path} yet — "
                "teach it something and run a training step first."
            )
        checkpoint = torch.load(path, map_location="cpu")
        self._config = GPTConfig(**checkpoint["config"])
        self._model = GPT(self._config)
        self._model.load_state_dict(checkpoint["model"])
        self._model.eval()
        return self._model

    def _generate_sync(self, messages: list[dict[str, str]]) -> str:
        model = self._load()
        prompt = "\n".join(f"{m['role']}: {m['content']}" for m in messages)
        ids = tokenizer.encode(prompt)[-self._config.block_size :]
        idx = torch.tensor([ids], dtype=torch.long)
        out = model.generate(idx, max_new_tokens=100, temperature=0.9, top_k=40)
        generated_ids = out[0, len(ids) :].tolist()
        return tokenizer.decode(generated_ids)

    async def generate(self, messages: list[dict[str, str]]) -> str:
        return await asyncio.to_thread(self._generate_sync, messages)
