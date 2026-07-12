import pytest

from kafkaf.core.enrichment import store as enrichment_store
from kafkaf.core.skills import store as skills_store
from kafkaf.core.skills.calculator import CalculatorSkill
from kafkaf.core.skills.datetime_skill import DateTimeSkill
from kafkaf.core.skills.document_search import DocumentSearchSkill
from kafkaf.core.skills.files import FilesSkill
from kafkaf.core.skills.memory_search import MemorySearchSkill
from kafkaf.core.skills.reminders import RemindersSkill
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
