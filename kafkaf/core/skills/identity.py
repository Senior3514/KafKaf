from kafkaf.core.skills.base import Skill
from kafkaf.core.skills.sandbox import resolve_safe as _resolve_safe

_IDENTITY_FILE = "identity.md"
_DEFAULT_IDENTITY = (
    "# KafKaf's own identity\n\n"
    "This file doesn't exist yet. Nothing has been written here — this "
    "model starts with no self-description, the same way it starts with "
    "no taught facts. Use 'write <description>' to give it one, or let it "
    "propose and refine its own via conversation.\n"
)


class IdentitySkill(Skill):
    name = "identity"
    description = (
        "A persistent self-description file, confined to the sandboxed workspace — "
        "who KafKaf is, what it's learned about itself, how it wants to come across. "
        "Usage: 'show' to read it, or 'write <full new description>' to replace it."
    )

    async def run(self, arg: str) -> str:
        arg = arg.strip()

        if arg == "show" or arg == "":
            path = _resolve_safe(_IDENTITY_FILE)
            if not path.exists():
                return _DEFAULT_IDENTITY
            return path.read_text(encoding="utf-8")

        if arg.startswith("write "):
            content = arg[len("write ") :].strip()
            if not content:
                return "error: empty description"
            path = _resolve_safe(_IDENTITY_FILE)
            path.write_text(content, encoding="utf-8")
            return "identity updated"

        return "error: unrecognized command — use 'show' or 'write <description>'"
