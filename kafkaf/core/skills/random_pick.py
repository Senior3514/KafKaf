import random

from kafkaf.core.skills.base import Skill


class RandomPickSkill(Skill):
    name = "random_pick"
    description = (
        "Pick randomly, for real decisions. Usage: 'roll <NdM>' (e.g. 'roll 2d6'), "
        "or a comma-separated list of options (e.g. 'pizza, sushi, tacos')."
    )

    async def run(self, arg: str) -> str:
        arg = arg.strip()
        if not arg:
            return "error: empty input"

        if arg.lower().startswith("roll "):
            spec = arg[len("roll ") :].strip().lower()
            try:
                count_str, sides_str = spec.split("d", 1)
                count, sides = int(count_str), int(sides_str)
            except ValueError:
                return "error: expected 'roll <N>d<M>', e.g. 'roll 2d6'"
            if not (1 <= count <= 100 and 2 <= sides <= 1000):
                return "error: count must be 1-100 and sides 2-1000"
            rolls = [random.randint(1, sides) for _ in range(count)]
            return f"{rolls} -> total {sum(rolls)}"

        options = [o.strip() for o in arg.split(",") if o.strip()]
        if len(options) < 2:
            return "error: give at least two comma-separated options, or 'roll <N>d<M>'"
        return random.choice(options)
