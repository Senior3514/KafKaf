from kafkaf.core.skills.base import Skill
from kafkaf.core.skills.browser_automate import BrowserAutomateSkill
from kafkaf.core.skills.browser_render import BrowserRenderSkill
from kafkaf.core.skills.calculator import CalculatorSkill
from kafkaf.core.skills.datetime_skill import DateTimeSkill
from kafkaf.core.skills.document_search import DocumentSearchSkill
from kafkaf.core.skills.files import FilesSkill
from kafkaf.core.skills.hash_text import HashTextSkill
from kafkaf.core.skills.identity import IdentitySkill
from kafkaf.core.skills.journal import JournalSkill
from kafkaf.core.skills.memory_search import MemorySearchSkill
from kafkaf.core.skills.own_model_status import OwnModelStatusSkill
from kafkaf.core.skills.password_generator import PasswordGeneratorSkill
from kafkaf.core.skills.random_pick import RandomPickSkill
from kafkaf.core.skills.reminders import RemindersSkill
from kafkaf.core.skills.rss import RssSkill
from kafkaf.core.skills.run_code import RunCodeSkill
from kafkaf.core.skills.schedule import ScheduleSkill
from kafkaf.core.skills.system_info import SystemInfoSkill
from kafkaf.core.skills.text_diff import TextDiffSkill
from kafkaf.core.skills.text_stats import TextStatsSkill
from kafkaf.core.skills.unit_convert import UnitConvertSkill
from kafkaf.core.skills.weather import WeatherSkill
from kafkaf.core.skills.web_fetch import WebFetchSkill
from kafkaf.core.skills.web_search import WebSearchSkill

ALL_SKILLS: list[Skill] = [
    WebSearchSkill(),
    WebFetchSkill(),
    BrowserRenderSkill(),
    CalculatorSkill(),
    DateTimeSkill(),
    MemorySearchSkill(),
    FilesSkill(),
    DocumentSearchSkill(),
    RemindersSkill(),
    UnitConvertSkill(),
    RssSkill(),
    WeatherSkill(),
    SystemInfoSkill(),
    JournalSkill(),
    IdentitySkill(),
    ScheduleSkill(),
    OwnModelStatusSkill(),
    PasswordGeneratorSkill(),
    TextDiffSkill(),
    HashTextSkill(),
    RandomPickSkill(),
    TextStatsSkill(),
    RunCodeSkill(),
    BrowserAutomateSkill(),
]

SKILLS_BY_NAME: dict[str, Skill] = {skill.name: skill for skill in ALL_SKILLS}


async def run_due_schedules(now_iso: str) -> list[dict]:
    """Run every scheduled task whose time has come, mark it done, and
    return a record of what ran. Only ever dispatches a skill that's
    already in the registry (schedules can't name anything else — the
    schedule skill validates the name at creation), so this adds no new
    capability, just deferred execution of the existing, hand-written
    skill set. Callers gate on autonomy (see autopilot) before invoking
    this, exactly like any other skill run. A failing scheduled skill is
    recorded and marked done rather than left to retry forever."""
    from kafkaf.core.skills import store as skills_store

    ran: list[dict] = []
    for task in skills_store.due_schedules(now_iso):
        skill = SKILLS_BY_NAME.get(task["skill_name"])
        if skill is None:
            # The skill was removed since the task was scheduled — don't
            # wedge the queue on it.
            skills_store.complete_schedule(task["id"])
            ran.append({**task, "result": f"error: skill {task['skill_name']!r} no longer exists"})
            continue
        if skill.requires_approval:
            # Defense-in-depth: ScheduleSkill.add already refuses to
            # create a row naming a requires_approval skill, but skip it
            # here too in case one ever exists another way — an
            # unattended autopilot cycle has no human to click approve.
            skills_store.complete_schedule(task["id"])
            ran.append(
                {**task, "result": f"error: {task['skill_name']!r} requires human approval and cannot run unattended — skipped"}
            )
            continue
        try:
            result = await skill.run(task["skill_arg"])
        except Exception as exc:  # a bad scheduled run must not wedge the queue
            result = f"error: {exc}"
        skills_store.complete_schedule(task["id"])
        ran.append({**task, "result": result})
    return ran
