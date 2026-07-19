from datetime import datetime, timezone

import pytest

from kafkaf.core.skills import store as skills_store
from kafkaf.core.skills.registry import run_due_schedules
from kafkaf.core.skills.schedule import ScheduleSkill


@pytest.fixture(autouse=True)
def _isolated_storage(monkeypatch, tmp_path):
    monkeypatch.setattr("kafkaf.core.config.settings.db_path", str(tmp_path / "test.db"))
    monkeypatch.setattr(
        "kafkaf.core.config.settings.skills_workspace_dir", str(tmp_path / "workspace")
    )
    skills_store.init_db()
    yield


_FIXED_NOW = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def _skill_at(now):
    return ScheduleSkill(now_factory=lambda: now)


class TestScheduleSkill:
    @pytest.mark.asyncio
    async def test_add_relative_and_list(self):
        skill = _skill_at(_FIXED_NOW)
        add_result = await skill.run("add in 1h weather: Tel Aviv")
        assert "scheduled #" in add_result
        assert "weather" in add_result

        list_result = await skill.run("list")
        assert "weather: Tel Aviv" in list_result
        # 12:00 + 1h = 13:00
        assert "2026-01-01T13:00:00" in list_result

    @pytest.mark.asyncio
    async def test_empty_list(self):
        result = await _skill_at(_FIXED_NOW).run("list")
        assert result == "no scheduled tasks"

    @pytest.mark.asyncio
    async def test_add_absolute_iso(self):
        skill = _skill_at(_FIXED_NOW)
        result = await skill.run("add 2026-06-15T09:00:00 weather: Berlin")
        assert "scheduled #" in result
        assert "2026-06-15T09:00:00" in result

    @pytest.mark.asyncio
    async def test_unknown_skill_rejected(self):
        result = await _skill_at(_FIXED_NOW).run("add in 1h nonexistent: foo")
        assert result.startswith("error:")
        assert "unknown skill" in result

    @pytest.mark.asyncio
    async def test_cannot_schedule_schedule_itself(self):
        result = await _skill_at(_FIXED_NOW).run("add in 1h schedule: add in 1h weather: x")
        assert result.startswith("error:")

    @pytest.mark.asyncio
    async def test_bad_time_format_rejected(self):
        result = await _skill_at(_FIXED_NOW).run("add sometime weather: Tel Aviv")
        assert result.startswith("error:")

    @pytest.mark.asyncio
    async def test_missing_colon_rejected(self):
        result = await _skill_at(_FIXED_NOW).run("add in 1h weather Tel Aviv")
        assert result.startswith("error:")

    @pytest.mark.asyncio
    async def test_cancel(self):
        skill = _skill_at(_FIXED_NOW)
        add_result = await skill.run("add in 1h calculator: 1+1")
        schedule_id = int(add_result.split("#")[1].split(":")[0])
        cancel_result = await skill.run(f"cancel {schedule_id}")
        assert "cancelled" in cancel_result
        assert await skill.run("list") == "no scheduled tasks"

    @pytest.mark.asyncio
    async def test_cancel_nonexistent(self):
        result = await _skill_at(_FIXED_NOW).run("cancel 999")
        assert "no scheduled task" in result

    @pytest.mark.asyncio
    async def test_cannot_schedule_approval_gated_skill(self):
        result = await _skill_at(_FIXED_NOW).run("add in 1h run_code: print(1)")
        assert result.startswith("error:")
        assert "human approval" in result
        assert await _skill_at(_FIXED_NOW).run("list") == "no scheduled tasks"


class TestRunDueSchedules:
    @pytest.mark.asyncio
    async def test_runs_only_due_tasks(self):
        skill = _skill_at(_FIXED_NOW)
        # Due in 1h and in 3h from the fixed now.
        await skill.run("add in 1h calculator: 2*3")
        await skill.run("add in 3h calculator: 10*10")

        # 2h later: only the first is due.
        two_hours_later = "2026-01-01T14:00:00+00:00"
        ran = await run_due_schedules(two_hours_later)
        assert len(ran) == 1
        assert ran[0]["skill_name"] == "calculator"
        assert ran[0]["result"] == "6"

        # The still-future task remains open.
        remaining = skills_store.list_schedules()
        assert len(remaining) == 1
        assert remaining[0]["skill_arg"] == "10*10"

    @pytest.mark.asyncio
    async def test_completed_tasks_do_not_run_again(self):
        skill = _skill_at(_FIXED_NOW)
        await skill.run("add in 1h calculator: 5+5")
        later = "2026-01-01T23:59:00+00:00"
        first = await run_due_schedules(later)
        assert len(first) == 1
        second = await run_due_schedules(later)
        assert second == []

    @pytest.mark.asyncio
    async def test_failing_scheduled_skill_is_marked_done_not_retried(self):
        skill = _skill_at(_FIXED_NOW)
        # calculator with invalid input returns an "error:" string (doesn't raise),
        # but the task should still be marked done and not linger.
        await skill.run("add in 1h calculator: not math")
        later = "2026-01-01T23:59:00+00:00"
        ran = await run_due_schedules(later)
        assert len(ran) == 1
        assert ran[0]["result"].startswith("error:")
        assert skills_store.list_schedules() == []

    @pytest.mark.asyncio
    async def test_approval_gated_skill_row_is_skipped_never_executed(self):
        # Simulates a row inserted another way, bypassing ScheduleSkill.add's
        # own guard — run_due_schedules must still refuse to run it
        # unattended, since no one can click approve for a scheduled fire.
        skills_store.add_schedule("run_code", "print('should never run')", "2026-01-01T13:00:00+00:00")
        later = "2026-01-01T23:59:00+00:00"
        ran = await run_due_schedules(later)
        assert len(ran) == 1
        assert ran[0]["result"].startswith("error:")
        assert "human approval" in ran[0]["result"]
        assert skills_store.list_schedules() == []
