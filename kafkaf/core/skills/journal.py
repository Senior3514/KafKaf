from datetime import datetime, timezone

from kafkaf.core.skills.base import Skill
from kafkaf.core.skills.sandbox import resolve_safe as _resolve_safe

_JOURNAL_FILE = "journal.txt"
MAX_ENTRIES_SHOWN = 20


class JournalSkill(Skill):
    name = "journal"
    description = (
        "A private, timestamped notes log confined to the sandboxed workspace. "
        "Usage: 'add <note>' to append an entry, or 'show' for the most recent entries."
    )

    async def run(self, arg: str) -> str:
        arg = arg.strip()

        if arg == "show" or arg == "":
            path = _resolve_safe(_JOURNAL_FILE)
            if not path.exists():
                return "journal is empty"
            lines = path.read_text(encoding="utf-8").splitlines()
            return "\n".join(lines[-MAX_ENTRIES_SHOWN:])

        if arg.startswith("add "):
            note = arg[len("add ") :].strip()
            if not note:
                return "error: empty note"
            timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            path = _resolve_safe(_JOURNAL_FILE)
            with path.open("a", encoding="utf-8") as f:
                f.write(f"[{timestamp}] {note}\n")
            return f"logged: {note}"

        return "error: unrecognized command — use 'add <note>' or 'show'"
