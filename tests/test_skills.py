import pytest

from kafkaf.core.enrichment import store as enrichment_store
from kafkaf.core.skills import store as skills_store
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
from kafkaf.core.skills.system_info import SystemInfoSkill
from kafkaf.core.skills.text_diff import TextDiffSkill
from kafkaf.core.skills.text_stats import TextStatsSkill
from kafkaf.core.skills.unit_convert import UnitConvertSkill


@pytest.fixture(autouse=True)
def _isolated_storage(monkeypatch, tmp_path):
    monkeypatch.setattr("kafkaf.core.config.settings.db_path", str(tmp_path / "test.db"))
    monkeypatch.setattr(
        "kafkaf.core.config.settings.skills_workspace_dir", str(tmp_path / "workspace")
    )
    skills_store.init_db()
    enrichment_store.init_db()
    yield


class TestCalculator:
    @pytest.mark.asyncio
    async def test_basic_arithmetic(self):
        assert await CalculatorSkill().run("2 * (3 + 4)") == "14"

    @pytest.mark.asyncio
    async def test_functions_and_constants(self):
        assert await CalculatorSkill().run("sqrt(16) + round(pi)") == "7.0"

    @pytest.mark.asyncio
    async def test_division_by_zero(self):
        result = await CalculatorSkill().run("1 / 0")
        assert result.startswith("error:")

    @pytest.mark.asyncio
    async def test_rejects_arbitrary_code(self):
        result = await CalculatorSkill().run('__import__("os").system("echo pwned")')
        assert result.startswith("error:")

    @pytest.mark.asyncio
    async def test_rejects_name_access(self):
        result = await CalculatorSkill().run("open('/etc/passwd').read()")
        assert result.startswith("error:")


class TestUnitConvert:
    @pytest.mark.asyncio
    async def test_length(self):
        result = await UnitConvertSkill().run("1 km to m")
        assert result == "1000"

    @pytest.mark.asyncio
    async def test_temperature(self):
        result = await UnitConvertSkill().run("0 c to f")
        assert result == "32"

    @pytest.mark.asyncio
    async def test_mismatched_units_error(self):
        result = await UnitConvertSkill().run("10 kg to miles")
        assert result.startswith("error:")

    @pytest.mark.asyncio
    async def test_bad_format_error(self):
        result = await UnitConvertSkill().run("not a conversion")
        assert result.startswith("error:")


class TestDateTime:
    @pytest.mark.asyncio
    async def test_returns_a_year(self):
        result = await DateTimeSkill().run("")
        assert "UTC" in result


class TestFiles:
    @pytest.mark.asyncio
    async def test_write_then_read(self):
        write_result = await FilesSkill().run("write notes.txt\nhello world")
        assert "notes.txt" in write_result
        read_result = await FilesSkill().run("read notes.txt")
        assert read_result == "hello world"

    @pytest.mark.asyncio
    async def test_list(self):
        await FilesSkill().run("write a.txt\ncontent")
        result = await FilesSkill().run("list")
        assert "a.txt" in result

    @pytest.mark.asyncio
    async def test_read_missing_file(self):
        result = await FilesSkill().run("read nope.txt")
        assert result.startswith("error:")

    @pytest.mark.asyncio
    async def test_path_traversal_blocked(self):
        result = await FilesSkill().run("read ../../etc/passwd")
        assert "escapes" in result

    @pytest.mark.asyncio
    async def test_absolute_path_traversal_blocked(self):
        result = await FilesSkill().run("write /etc/passwd\npwned")
        assert "escapes" in result


class TestDocumentSearch:
    @pytest.mark.asyncio
    async def test_finds_matching_content_across_files(self):
        await FilesSkill().run("write notes.txt\nKafKaf is a private, self-hosted AI platform.")
        await FilesSkill().run("write other.txt\nThis file is about something unrelated.")
        result = await DocumentSearchSkill().run("private self-hosted")
        assert "notes.txt" in result
        assert "other.txt" not in result

    @pytest.mark.asyncio
    async def test_ranks_by_relevance(self):
        await FilesSkill().run("write a.txt\nkafkaf kafkaf kafkaf")
        await FilesSkill().run("write b.txt\nkafkaf appears once here")
        result = await DocumentSearchSkill().run("kafkaf")
        assert result.index("a.txt") < result.index("b.txt")

    @pytest.mark.asyncio
    async def test_ignores_unsupported_file_types(self):
        await FilesSkill().run("write image.png\nkafkaf binary-ish content")
        result = await DocumentSearchSkill().run("kafkaf")
        assert result == "no matching content found in the workspace"

    @pytest.mark.asyncio
    async def test_no_match(self):
        await FilesSkill().run("write notes.txt\nsomething else entirely")
        result = await DocumentSearchSkill().run("nonexistent query xyz")
        assert result == "no matching content found in the workspace"

    @pytest.mark.asyncio
    async def test_empty_query(self):
        result = await DocumentSearchSkill().run("")
        assert result.startswith("error:")


class TestReminders:
    @pytest.mark.asyncio
    async def test_add_list_done(self):
        skill = RemindersSkill()
        add_result = await skill.run("add buy milk")
        assert "buy milk" in add_result

        list_result = await skill.run("list")
        assert "buy milk" in list_result

        reminder_id = int(list_result.split(":")[0].lstrip("#"))
        done_result = await skill.run(f"done {reminder_id}")
        assert "done" in done_result

        list_after = await skill.run("list")
        assert "buy milk" not in list_after

    @pytest.mark.asyncio
    async def test_empty_list(self):
        result = await RemindersSkill().run("list")
        assert result == "no open reminders"


class TestMemorySearch:
    @pytest.mark.asyncio
    async def test_finds_taught_facts(self):
        enrichment_store.save_example("fact", "KafKaf", "about kafkaf", "KafKaf is private.")
        result = await MemorySearchSkill().run("kafkaf")
        assert "KafKaf is private." in result

    @pytest.mark.asyncio
    async def test_no_match(self):
        result = await MemorySearchSkill().run("nonexistent topic xyz")
        assert "nothing found" in result


class TestSystemInfo:
    @pytest.mark.asyncio
    async def test_returns_a_snapshot(self):
        result = await SystemInfoSkill().run("")
        assert "OS:" in result
        assert "Python:" in result
        assert "CPU cores:" in result
        assert "Disk:" in result


class TestJournal:
    @pytest.mark.asyncio
    async def test_empty_journal(self):
        result = await JournalSkill().run("show")
        assert result == "journal is empty"

    @pytest.mark.asyncio
    async def test_add_then_show(self):
        add_result = await JournalSkill().run("add fed the model a new fact")
        assert "fed the model a new fact" in add_result
        show_result = await JournalSkill().run("show")
        assert "fed the model a new fact" in show_result
        assert "UTC" in show_result

    @pytest.mark.asyncio
    async def test_empty_note_error(self):
        result = await JournalSkill().run("add ")
        assert result.startswith("error:")

    @pytest.mark.asyncio
    async def test_unrecognized_command(self):
        result = await JournalSkill().run("delete everything")
        assert result.startswith("error:")


class TestOwnModelStatus:
    @pytest.mark.asyncio
    async def test_never_trained(self):
        result = await OwnModelStatusSkill().run("")
        assert "never trained yet" in result
        assert "corpus: 0 examples" in result

    @pytest.mark.asyncio
    async def test_reports_corpus_size_after_teaching(self):
        enrichment_store.save_example("fact", "KafKaf", "about kafkaf", "KafKaf is private.")
        result = await OwnModelStatusSkill().run("")
        assert "corpus: 1 examples" in result


class TestPasswordGenerator:
    @pytest.mark.asyncio
    async def test_default_length(self):
        result = await PasswordGeneratorSkill().run("")
        assert len(result) == 20

    @pytest.mark.asyncio
    async def test_custom_length(self):
        result = await PasswordGeneratorSkill().run("32")
        assert len(result) == 32

    @pytest.mark.asyncio
    async def test_two_calls_differ(self):
        a = await PasswordGeneratorSkill().run("16")
        b = await PasswordGeneratorSkill().run("16")
        assert a != b

    @pytest.mark.asyncio
    async def test_out_of_range_error(self):
        result = await PasswordGeneratorSkill().run("4")
        assert result.startswith("error:")

    @pytest.mark.asyncio
    async def test_non_numeric_error(self):
        result = await PasswordGeneratorSkill().run("abc")
        assert result.startswith("error:")


class TestTextDiff:
    @pytest.mark.asyncio
    async def test_finds_a_difference(self):
        result = await TextDiffSkill().run("hello world\n---\nhello there")
        assert "hello world" in result
        assert "hello there" in result

    @pytest.mark.asyncio
    async def test_identical_text_no_diff(self):
        result = await TextDiffSkill().run("same\n---\nsame")
        assert result == "no differences"

    @pytest.mark.asyncio
    async def test_bad_format_error(self):
        result = await TextDiffSkill().run("no separator here")
        assert result.startswith("error:")


class TestHashText:
    @pytest.mark.asyncio
    async def test_default_sha256(self):
        result = await HashTextSkill().run("hello")
        assert result == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"

    @pytest.mark.asyncio
    async def test_explicit_md5(self):
        result = await HashTextSkill().run("md5 hello")
        assert result == "5d41402abc4b2a76b9719d911017c592"

    @pytest.mark.asyncio
    async def test_empty_error(self):
        result = await HashTextSkill().run("")
        assert result.startswith("error:")


class TestRandomPick:
    @pytest.mark.asyncio
    async def test_picks_from_options(self):
        result = await RandomPickSkill().run("pizza, sushi, tacos")
        assert result in ("pizza", "sushi", "tacos")

    @pytest.mark.asyncio
    async def test_roll_dice(self):
        result = await RandomPickSkill().run("roll 2d6")
        assert "total" in result

    @pytest.mark.asyncio
    async def test_bad_roll_format(self):
        result = await RandomPickSkill().run("roll xyz")
        assert result.startswith("error:")

    @pytest.mark.asyncio
    async def test_single_option_error(self):
        result = await RandomPickSkill().run("onlyone")
        assert result.startswith("error:")


class TestTextStats:
    @pytest.mark.asyncio
    async def test_counts(self):
        result = await TextStatsSkill().run("Hello world. How are you?")
        assert "words: 5" in result
        assert "sentences: 2" in result

    @pytest.mark.asyncio
    async def test_empty_error(self):
        result = await TextStatsSkill().run("")
        assert result.startswith("error:")
