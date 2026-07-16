import difflib

from kafkaf.core.skills.base import Skill


class TextDiffSkill(Skill):
    name = "text_diff"
    description = (
        "Compare two texts and show the differences, line by line. Usage: "
        "'<text A>\\n---\\n<text B>'."
    )

    async def run(self, arg: str) -> str:
        if "\n---\n" not in arg:
            return "error: expected '<text A>\\n---\\n<text B>'"
        text_a, text_b = arg.split("\n---\n", 1)
        diff = list(
            difflib.unified_diff(
                text_a.splitlines(), text_b.splitlines(), lineterm="", fromfile="A", tofile="B"
            )
        )
        if not diff:
            return "no differences"
        return "\n".join(diff)
