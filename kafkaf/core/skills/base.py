from abc import ABC, abstractmethod


class Skill(ABC):
    """A single tool a brain can invoke via the ReAct loop (see loop.py).

    Each skill takes one plain-text argument and returns one plain-text
    observation — deliberately simple so any brain (including small local
    models) can reliably format a call, unlike multi-field JSON tool calls.
    """

    name: str
    description: str

    @abstractmethod
    async def run(self, arg: str) -> str:
        """Execute the skill and return an observation string."""
