import re

from kafkaf.core.skills.base import Skill

_WORDS_PER_MINUTE = 200


class TextStatsSkill(Skill):
    name = "text_stats"
    description = "Word/character/sentence count and estimated reading time for a piece of text."

    async def run(self, arg: str) -> str:
        text = arg.strip()
        if not text:
            return "error: empty text"

        words = text.split()
        sentences = [s for s in re.split(r"[.!?]+", text) if s.strip()]
        reading_minutes = max(1, round(len(words) / _WORDS_PER_MINUTE))

        return (
            f"words: {len(words)}\n"
            f"characters: {len(text)}\n"
            f"sentences: {len(sentences)}\n"
            f"estimated reading time: ~{reading_minutes} min"
        )
