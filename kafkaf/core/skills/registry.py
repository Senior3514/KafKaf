from kafkaf.core.skills.base import Skill
from kafkaf.core.skills.calculator import CalculatorSkill
from kafkaf.core.skills.datetime_skill import DateTimeSkill
from kafkaf.core.skills.files import FilesSkill
from kafkaf.core.skills.memory_search import MemorySearchSkill
from kafkaf.core.skills.reminders import RemindersSkill
from kafkaf.core.skills.rss import RssSkill
from kafkaf.core.skills.unit_convert import UnitConvertSkill
from kafkaf.core.skills.weather import WeatherSkill
from kafkaf.core.skills.web_fetch import WebFetchSkill
from kafkaf.core.skills.web_search import WebSearchSkill

ALL_SKILLS: list[Skill] = [
    WebSearchSkill(),
    WebFetchSkill(),
    CalculatorSkill(),
    DateTimeSkill(),
    MemorySearchSkill(),
    FilesSkill(),
    RemindersSkill(),
    UnitConvertSkill(),
    RssSkill(),
    WeatherSkill(),
]

SKILLS_BY_NAME: dict[str, Skill] = {skill.name: skill for skill in ALL_SKILLS}
