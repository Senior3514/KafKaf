from datetime import datetime, timezone

from kafkaf.core.skills.base import Skill


class DateTimeSkill(Skill):
    name = "current_datetime"
    description = "Get the current date and time (UTC). Argument is ignored."

    async def run(self, arg: str) -> str:
        now = datetime.now(timezone.utc)
        return now.strftime("%Y-%m-%d %H:%M:%S UTC (%A)")
