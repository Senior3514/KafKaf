from abc import ABC, abstractmethod
from collections.abc import AsyncIterator


class Brain(ABC):
    """A single model adapter. The council routes chat turns to one or more of these."""

    name: str

    @abstractmethod
    async def generate(self, messages: list[dict[str, str]]) -> str:
        """Generate a reply given a list of {"role": ..., "content": ...} messages."""

    async def generate_stream(self, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        """Default: no real streaming — yields the complete reply as one
        chunk. Only OllamaBrain overrides this today with real per-token
        streaming; extending the other brains is real, separate future
        work (see docs/ROADMAP.md)."""
        yield await self.generate(messages)
