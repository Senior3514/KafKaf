from kafkaf.core.skills.base import Skill
from kafkaf.core.skills.calculator import CalculatorSkill
from kafkaf.core.skills.datetime_skill import DateTimeSkill
from kafkaf.core.skills.document_search import DocumentSearchSkill
from kafkaf.core.skills.files import FilesSkill
from kafkaf.core.skills.hash_text import HashTextSkill
from kafkaf.core.skills.journal import JournalSkill
from kafkaf.core.skills.memory_search import MemorySearchSkill
from kafkaf.core.skills.own_model_status import OwnModelStatusSkill
from kafkaf.core.skills.password_generator import PasswordGeneratorSkill
from kafkaf.core.skills.random_pick import RandomPickSkill
from kafkaf.core.skills.reminders import RemindersSkill
from kafkaf.core.skills.rss import RssSkill
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
    OwnModelStatusSkill(),
    PasswordGeneratorSkill(),
    TextDiffSkill(),
    HashTextSkill(),
    RandomPickSkill(),
    TextStatsSkill(),
]

SKILLS_BY_NAME: dict[str, Skill] = {skill.name: skill for skill in ALL_SKILLS}
