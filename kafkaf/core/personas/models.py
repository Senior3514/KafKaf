from dataclasses import dataclass


@dataclass(frozen=True)
class Persona:
    key: str
    name: str
    system_prompt: str
