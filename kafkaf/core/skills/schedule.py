"""Schedule a *specific, already-existing* skill to run once at a future
time — e.g. "check the weather every morning and log it" becomes a real,
deferred action without opening any general unattended code execution.
Deliberately narrow: it can only trigger a skill that's already in the
registry (the same fixed, hand-written set the ReAct loop uses), with a
string argument — never arbitrary code, never a new capability. The
autopilot loop runs anything that's due (see run_due_schedules), gated by
the same autonomy level as every other skill, so at 'observe' nothing
fires.
"""

import re
from datetime import datetime, timedelta, timezone

from kafkaf.core.skills import store as skills_store
from kafkaf.core.skills.base import Skill

_REL_RE = re.compile(r"^in\s+(\d+)\s*([mhd])$", re.IGNORECASE)
_UNIT_SECONDS = {"m": 60, "h": 3600, "d": 86400}


def _parse_when(when: str, now: datetime) -> datetime:
    """Accepts 'in 30m' / 'in 2h' / 'in 1d' (relative) or a plain ISO-8601
    timestamp (absolute). Returns a timezone-aware UTC datetime, or raises
    ValueError with a clear message."""
    when = when.strip()
    match = _REL_RE.match(when)
    if match:
        amount = int(match.group(1))
        unit = match.group(2).lower()
        return now + timedelta(seconds=amount * _UNIT_SECONDS[unit])

    try:
        parsed = datetime.fromisoformat(when)
    except ValueError as exc:
        raise ValueError(
            "expected a time like 'in 30m', 'in 2h', 'in 1d', or an ISO-8601 timestamp"
        ) from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


class ScheduleSkill(Skill):
    name = "schedule"
    description = (
        "Schedule another skill to run once at a future time. "
        "Usage: 'add <when> <skill>: <arg>' (when is 'in 30m'/'in 2h'/'in 1d' or an "
        "ISO timestamp; e.g. 'add in 1h weather: Tel Aviv'), 'list', or 'cancel <id>'."
    )

    def __init__(self, now_factory=None):
        # Injectable clock so tests are deterministic; defaults to real UTC now.
        self._now = now_factory or (lambda: datetime.now(timezone.utc))

    async def run(self, arg: str) -> str:
        arg = arg.strip()

        if arg in ("", "list"):
            items = skills_store.list_schedules()
            if not items:
                return "no scheduled tasks"
            return "\n".join(
                f"#{i['id']}: {i['skill_name']}: {i['skill_arg']} @ {i['run_at']}" for i in items
            )

        if arg.startswith("cancel "):
            try:
                schedule_id = int(arg[len("cancel ") :].strip())
            except ValueError:
                return "error: expected a numeric schedule id"
            ok = skills_store.complete_schedule(schedule_id)
            return f"cancelled #{schedule_id}" if ok else f"no scheduled task #{schedule_id}"

        if arg.startswith("add "):
            body = arg[len("add ") :].strip()
            # Split "<when> <skill>: <arg>". The ':' can't just be the first
            # one in the string — an absolute ISO timestamp ("09:00:00")
            # contains colons too. The real separator is the colon
            # immediately following a whitespace-delimited word that is a
            # registered skill name; find the first such split point.
            from kafkaf.core.skills.registry import SKILLS_BY_NAME

            split = None
            colon_words = []
            for match in re.finditer(r"(\S+):", body):
                candidate = match.group(1)
                colon_words.append(candidate)
                if candidate in SKILLS_BY_NAME:
                    split = (body[: match.start()].strip(), candidate, body[match.end() :].strip())
                    break
            if split is None:
                # A `word:` that isn't a purely-numeric ISO time fragment is
                # almost certainly a misspelled/unknown skill name — say so.
                named = next((w for w in colon_words if not w.replace(":", "").isdigit()), None)
                if named:
                    return f"error: unknown skill {named!r} — see the skills list for valid names"
                return "error: expected 'add <when> <skill>: <arg>' (no skill name before ':')"
            when_str, skill_name, skill_arg = split

            if not when_str:
                return "error: expected 'add <when> <skill>: <arg>' (missing the time)"
            if skill_name == "schedule":
                return "error: a scheduled task can't itself be 'schedule'"

            try:
                run_at = _parse_when(when_str, self._now())
            except ValueError as exc:
                return f"error: {exc}"

            run_at_iso = run_at.isoformat()
            schedule_id = skills_store.add_schedule(skill_name, skill_arg, run_at_iso)
            return f"scheduled #{schedule_id}: {skill_name}: {skill_arg} @ {run_at_iso}"

        return "error: unrecognized command — use 'add <when> <skill>: <arg>', 'list', or 'cancel <id>'"
