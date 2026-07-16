import secrets
import string

from kafkaf.core.skills.base import Skill

MIN_LENGTH = 8
MAX_LENGTH = 128
DEFAULT_LENGTH = 20


class PasswordGeneratorSkill(Skill):
    name = "password_generator"
    description = (
        "Generate a cryptographically secure random password. Usage: "
        "'<length>' (default 20, 8-128) using Python's secrets module, never a weak PRNG."
    )

    async def run(self, arg: str) -> str:
        arg = arg.strip()
        length = DEFAULT_LENGTH
        if arg:
            try:
                length = int(arg)
            except ValueError:
                return "error: length must be a whole number"
        if not MIN_LENGTH <= length <= MAX_LENGTH:
            return f"error: length must be between {MIN_LENGTH} and {MAX_LENGTH}"

        alphabet = string.ascii_letters + string.digits + "!@#$%^&*()-_=+"
        return "".join(secrets.choice(alphabet) for _ in range(length))
