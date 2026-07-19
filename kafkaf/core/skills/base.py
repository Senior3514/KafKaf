from abc import ABC, abstractmethod


class Skill(ABC):
    """A single tool a brain can invoke via the ReAct loop (see loop.py).

    Each skill takes one plain-text argument and returns one plain-text
    observation — deliberately simple so any brain (including small local
    models) can reliably format a call, unlike multi-field JSON tool calls.
    """

    name: str
    description: str

    # Whether this skill can ever mutate state (write a file, add a
    # reminder/journal entry/schedule, change identity.md). Conservative
    # and classified per-skill, not per-argument — a skill that supports
    # both read and write commands (e.g. files' "read"/"write") is still
    # marked write-capable, since the gate exists to make the mutating
    # subset controllable, not to parse intent out of free-text args.
    read_only: bool = True

    @abstractmethod
    async def run(self, arg: str) -> str:
        """Execute the skill and return an observation string."""
