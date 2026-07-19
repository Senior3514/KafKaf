from kafkaf.core.skills import store as reminders_store
from kafkaf.core.skills.base import Skill


class RemindersSkill(Skill):
    name = "reminders"
    read_only = False  # supports "add <text>" / "done <id>"
    description = "Manage a persistent reminder list. Usage: 'add <text>', 'list', or 'done <id>'."

    async def run(self, arg: str) -> str:
        arg = arg.strip()

        if arg.startswith("add "):
            text = arg[len("add ") :].strip()
            if not text:
                return "error: nothing to add"
            reminder_id = reminders_store.add_reminder(text)
            return f"added reminder #{reminder_id}: {text}"

        if arg in ("", "list"):
            items = reminders_store.list_reminders()
            if not items:
                return "no open reminders"
            return "\n".join(f"#{item['id']}: {item['text']}" for item in items)

        if arg.startswith("done "):
            try:
                reminder_id = int(arg[len("done ") :].strip())
            except ValueError:
                return "error: expected a numeric reminder id"
            ok = reminders_store.complete_reminder(reminder_id)
            return f"marked #{reminder_id} done" if ok else f"no reminder #{reminder_id}"

        return "error: unrecognized command — use 'add <text>', 'list', or 'done <id>'"
