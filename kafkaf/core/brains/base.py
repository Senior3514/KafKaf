from abc import ABC, abstractmethod


class Brain(ABC):
    """A single model adapter. The council routes chat turns to one or more of these."""

    name: str

    @abstractmethod
    async def generate(self, messages: list[dict[str, str]]) -> str:
        """Generate a reply given a list of {"role": ..., "content": ...} messages."""
