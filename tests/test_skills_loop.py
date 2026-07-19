import pytest

from kafkaf.core.audit import store as audit_store
from kafkaf.core.brains.base import Brain
from kafkaf.core.skills.loop import run_skill_loop


@pytest.fixture(autouse=True)
def _isolated_audit_db(monkeypatch, tmp_path):
    monkeypatch.setattr("kafkaf.core.config.settings.db_path", str(tmp_path / "test.db"))
    audit_store.init_db()
    yield


class ScriptedBrain(Brain):
    name = "scripted"

    def __init__(self, replies: list[str]):
        self._replies = list(replies)
        self.seen_messages: list[list[dict[str, str]]] = []

    async def generate(self, messages: list[dict[str, str]]) -> str:
        self.seen_messages.append([dict(m) for m in messages])
        return self._replies.pop(0)


@pytest.mark.asyncio
async def test_no_action_returns_reply_directly():
    brain = ScriptedBrain(["just a plain answer, no tools needed"])
    result = await run_skill_loop(brain, [{"role": "user", "content": "hi"}])
    assert result == "just a plain answer, no tools needed"


@pytest.mark.asyncio
async def test_action_executes_and_final_answer_returned():
    brain = ScriptedBrain(["ACTION: calculator: 2 + 2", "FINAL ANSWER: it's 4"])
    result = await run_skill_loop(brain, [{"role": "user", "content": "what is 2+2?"}])
    assert result == "it's 4"
    # second call should have seen the observation with the real computed result
    assert "OBSERVATION: 4" in brain.seen_messages[1][-1]["content"]
    events = audit_store.recent_events()
    assert any(e["event_type"] == "skill" and e["actor"] == "calculator" for e in events)


@pytest.mark.asyncio
async def test_unknown_skill_becomes_error_observation():
    brain = ScriptedBrain(["ACTION: not_a_real_skill: whatever", "FINAL ANSWER: gave up gracefully"])
    result = await run_skill_loop(brain, [{"role": "user", "content": "hi"}])
    assert result == "gave up gracefully"
    assert "unknown tool" in brain.seen_messages[1][-1]["content"]


@pytest.mark.asyncio
async def test_broken_skill_does_not_crash_the_loop(monkeypatch):
    class BrokenSkill:
        name = "broken"
        description = "a skill that always fails, for testing error handling"
        read_only = True

        async def run(self, arg: str) -> str:
            raise RuntimeError("kaboom")

    import kafkaf.core.skills.loop as loop_module

    monkeypatch.setitem(loop_module.SKILLS_BY_NAME, "broken", BrokenSkill())

    brain = ScriptedBrain(["ACTION: broken: whatever", "FINAL ANSWER: recovered"])
    result = await run_skill_loop(brain, [{"role": "user", "content": "hi"}])
    assert result == "recovered"
    assert "kaboom" in brain.seen_messages[1][-1]["content"]


@pytest.mark.asyncio
async def test_write_skill_blocked_at_manual_mode(monkeypatch, tmp_path):
    monkeypatch.setattr("kafkaf.core.config.settings.write_skills_mode", "manual")
    monkeypatch.setattr(
        "kafkaf.core.config.settings.skills_workspace_dir", str(tmp_path / "workspace")
    )
    brain = ScriptedBrain(
        ["ACTION: journal: add tried to write something", "FINAL ANSWER: blocked"]
    )
    result = await run_skill_loop(brain, [{"role": "user", "content": "hi"}])
    assert result == "blocked"
    observation = brain.seen_messages[1][-1]["content"]
    assert "manual" in observation
    assert "not executed" in observation
    events = audit_store.recent_events()
    assert any(e["event_type"] == "skill_write_blocked" and e["actor"] == "journal" for e in events)


@pytest.mark.asyncio
async def test_read_only_skill_unaffected_by_manual_write_mode(monkeypatch):
    monkeypatch.setattr("kafkaf.core.config.settings.write_skills_mode", "manual")
    brain = ScriptedBrain(["ACTION: calculator: 3 + 4", "FINAL ANSWER: it's 7"])
    result = await run_skill_loop(brain, [{"role": "user", "content": "hi"}])
    assert result == "it's 7"
    assert "OBSERVATION: 7" in brain.seen_messages[1][-1]["content"]


@pytest.mark.asyncio
async def test_write_skill_runs_at_assisted_mode_and_is_flagged(monkeypatch, tmp_path):
    monkeypatch.setattr("kafkaf.core.config.settings.write_skills_mode", "assisted")
    monkeypatch.setattr(
        "kafkaf.core.config.settings.skills_workspace_dir", str(tmp_path / "workspace")
    )
    brain = ScriptedBrain(["ACTION: journal: add a real note", "FINAL ANSWER: logged"])
    result = await run_skill_loop(brain, [{"role": "user", "content": "hi"}])
    assert result == "logged"
    assert "logged: a real note" in brain.seen_messages[1][-1]["content"]
    events = audit_store.recent_events()
    assert any(e["event_type"] == "skill_write" and e["actor"] == "journal" for e in events)


@pytest.mark.asyncio
async def test_write_skill_runs_at_autonomous_mode_as_plain_skill_event(monkeypatch, tmp_path):
    monkeypatch.setattr("kafkaf.core.config.settings.write_skills_mode", "autonomous")
    monkeypatch.setattr(
        "kafkaf.core.config.settings.skills_workspace_dir", str(tmp_path / "workspace")
    )
    brain = ScriptedBrain(["ACTION: journal: add another note", "FINAL ANSWER: logged"])
    result = await run_skill_loop(brain, [{"role": "user", "content": "hi"}])
    assert result == "logged"
    events = audit_store.recent_events()
    assert any(e["event_type"] == "skill" and e["actor"] == "journal" for e in events)
    assert not any(e["event_type"] == "skill_write" for e in events)


@pytest.mark.asyncio
async def test_max_iterations_gives_up():
    brain = ScriptedBrain(["ACTION: calculator: 1 + 1"] * 10)
    result = await run_skill_loop(brain, [{"role": "user", "content": "hi"}])
    assert "wasn't able to finish" in result


@pytest.mark.asyncio
async def test_preamble_added_to_system_message():
    brain = ScriptedBrain(["plain answer"])
    await run_skill_loop(brain, [{"role": "system", "content": "You are helpful."}, {"role": "user", "content": "hi"}])
    system_content = brain.seen_messages[0][0]["content"]
    assert "You are helpful." in system_content
    assert "ACTION:" in system_content
