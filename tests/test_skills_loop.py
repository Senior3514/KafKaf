import pytest

from kafkaf.core.audit import store as audit_store
from kafkaf.core.brains.base import Brain
from kafkaf.core.skills import store as skills_store
from kafkaf.core.skills.loop import resume_skill_loop, run_skill_loop


@pytest.fixture(autouse=True)
def _isolated_audit_db(monkeypatch, tmp_path):
    monkeypatch.setattr("kafkaf.core.config.settings.db_path", str(tmp_path / "test.db"))
    audit_store.init_db()
    skills_store.init_db()
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
    assert result.reply == "just a plain answer, no tools needed"
    assert result.pending_approval is None


@pytest.mark.asyncio
async def test_action_executes_and_final_answer_returned():
    brain = ScriptedBrain(["ACTION: calculator: 2 + 2", "FINAL ANSWER: it's 4"])
    result = await run_skill_loop(brain, [{"role": "user", "content": "what is 2+2?"}])
    assert result.reply == "it's 4"
    # second call should have seen the observation with the real computed result
    assert "OBSERVATION: 4" in brain.seen_messages[1][-1]["content"]
    events = audit_store.recent_events()
    assert any(e["event_type"] == "skill" and e["actor"] == "calculator" for e in events)


@pytest.mark.asyncio
async def test_unknown_skill_becomes_error_observation():
    brain = ScriptedBrain(["ACTION: not_a_real_skill: whatever", "FINAL ANSWER: gave up gracefully"])
    result = await run_skill_loop(brain, [{"role": "user", "content": "hi"}])
    assert result.reply == "gave up gracefully"
    assert "unknown tool" in brain.seen_messages[1][-1]["content"]


@pytest.mark.asyncio
async def test_broken_skill_does_not_crash_the_loop(monkeypatch):
    class BrokenSkill:
        name = "broken"
        description = "a skill that always fails, for testing error handling"
        read_only = True
        requires_approval = False

        async def run(self, arg: str) -> str:
            raise RuntimeError("kaboom")

    import kafkaf.core.skills.loop as loop_module

    monkeypatch.setitem(loop_module.SKILLS_BY_NAME, "broken", BrokenSkill())

    brain = ScriptedBrain(["ACTION: broken: whatever", "FINAL ANSWER: recovered"])
    result = await run_skill_loop(brain, [{"role": "user", "content": "hi"}])
    assert result.reply == "recovered"
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
    assert result.reply == "blocked"
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
    assert result.reply == "it's 7"
    assert "OBSERVATION: 7" in brain.seen_messages[1][-1]["content"]


@pytest.mark.asyncio
async def test_write_skill_runs_at_assisted_mode_and_is_flagged(monkeypatch, tmp_path):
    monkeypatch.setattr("kafkaf.core.config.settings.write_skills_mode", "assisted")
    monkeypatch.setattr(
        "kafkaf.core.config.settings.skills_workspace_dir", str(tmp_path / "workspace")
    )
    brain = ScriptedBrain(["ACTION: journal: add a real note", "FINAL ANSWER: logged"])
    result = await run_skill_loop(brain, [{"role": "user", "content": "hi"}])
    assert result.reply == "logged"
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
    assert result.reply == "logged"
    events = audit_store.recent_events()
    assert any(e["event_type"] == "skill" and e["actor"] == "journal" for e in events)
    assert not any(e["event_type"] == "skill_write" for e in events)


@pytest.mark.asyncio
async def test_max_iterations_gives_up():
    brain = ScriptedBrain(["ACTION: calculator: 1 + 1"] * 10)
    result = await run_skill_loop(brain, [{"role": "user", "content": "hi"}])
    assert "wasn't able to finish" in result.reply


@pytest.mark.asyncio
async def test_preamble_added_to_system_message():
    brain = ScriptedBrain(["plain answer"])
    await run_skill_loop(brain, [{"role": "system", "content": "You are helpful."}, {"role": "user", "content": "hi"}])
    system_content = brain.seen_messages[0][0]["content"]
    assert "You are helpful." in system_content
    assert "ACTION:" in system_content


class _FakeApprovalSkill:
    """A requires_approval skill whose real execution just records that it
    ran, so tests can assert it was NOT called until approved."""

    name = "fake_gated"
    description = "a fake approval-gated skill for testing the pause/resume mechanism"
    read_only = False
    requires_approval = True

    def __init__(self):
        self.run_calls: list[str] = []

    async def run(self, arg: str) -> str:
        self.run_calls.append(arg)
        return f"did the thing with {arg}"


@pytest.fixture
def fake_gated_skill(monkeypatch):
    import kafkaf.core.skills.loop as loop_module

    skill = _FakeApprovalSkill()
    monkeypatch.setitem(loop_module.SKILLS_BY_NAME, "fake_gated", skill)
    return skill


@pytest.mark.asyncio
async def test_approval_gated_skill_pauses_without_executing(fake_gated_skill):
    brain = ScriptedBrain(["ACTION: fake_gated: do the risky thing"])
    result = await run_skill_loop(
        brain, [{"role": "user", "content": "hi"}], session_id="s1", user_message="hi"
    )
    assert result.reply is None
    assert result.pending_approval is not None
    assert result.pending_approval.skill_name == "fake_gated"
    assert result.pending_approval.skill_arg == "do the risky thing"
    assert fake_gated_skill.run_calls == []  # never actually executed

    row = skills_store.get_approval(result.pending_approval.approval_id)
    assert row["status"] == "pending"
    assert row["session_id"] == "s1"
    assert row["skill_name"] == "fake_gated"


@pytest.mark.asyncio
async def test_resume_after_approval_executes_and_continues(fake_gated_skill):
    brain = ScriptedBrain(["ACTION: fake_gated: do it", "FINAL ANSWER: done!"])
    paused = await run_skill_loop(
        brain, [{"role": "user", "content": "hi"}], session_id="s1", user_message="hi"
    )
    approval_id = paused.pending_approval.approval_id

    row = skills_store.claim_approval(approval_id, "approved")
    assert row is not None
    import json

    observation = await fake_gated_skill.run(row["skill_arg"])
    conversation = json.loads(row["conversation_json"])
    conversation.append({"role": "user", "content": f"OBSERVATION: {observation}"})

    result = await resume_skill_loop(
        brain, conversation, row["iterations_used"], session_id="s1", user_message="hi", brain_spec=None
    )
    assert result.reply == "done!"
    assert fake_gated_skill.run_calls == ["do it"]


@pytest.mark.asyncio
async def test_resume_after_denial_continues_with_denial_observation(fake_gated_skill):
    brain = ScriptedBrain(["ACTION: fake_gated: do it", "FINAL ANSWER: ok, I won't"])
    paused = await run_skill_loop(
        brain, [{"role": "user", "content": "hi"}], session_id="s1", user_message="hi"
    )
    row = skills_store.claim_approval(paused.pending_approval.approval_id, "denied")
    assert row is not None

    import json

    conversation = json.loads(row["conversation_json"])
    conversation.append({"role": "user", "content": "OBSERVATION: error: user denied this action"})
    result = await resume_skill_loop(
        brain, conversation, row["iterations_used"], session_id="s1", user_message="hi", brain_spec=None
    )
    assert result.reply == "ok, I won't"
    assert fake_gated_skill.run_calls == []
    assert "OBSERVATION: error: user denied" in brain.seen_messages[1][-1]["content"]


@pytest.mark.asyncio
async def test_nested_approval_after_resume(fake_gated_skill):
    """Resuming from one approval can itself hit a second gated call."""
    brain = ScriptedBrain(["ACTION: fake_gated: first", "ACTION: fake_gated: second", "FINAL ANSWER: done"])
    paused = await run_skill_loop(
        brain, [{"role": "user", "content": "hi"}], session_id="s1", user_message="hi"
    )
    row = skills_store.claim_approval(paused.pending_approval.approval_id, "approved")
    import json

    observation = await fake_gated_skill.run(row["skill_arg"])
    conversation = json.loads(row["conversation_json"])
    conversation.append({"role": "user", "content": f"OBSERVATION: {observation}"})

    second = await resume_skill_loop(
        brain, conversation, row["iterations_used"], session_id="s1", user_message="hi", brain_spec=None
    )
    assert second.reply is None
    assert second.pending_approval is not None
    assert second.pending_approval.approval_id != paused.pending_approval.approval_id
    assert second.pending_approval.skill_arg == "second"


@pytest.mark.asyncio
async def test_iterations_used_carries_cumulatively_across_resume(fake_gated_skill):
    """MAX_ITERATIONS is enforced across the whole paused+resumed turn, not
    reset to a fresh budget on each resume: exactly MAX_ITERATIONS total
    generate() calls should exhaust the budget, however many separate
    pause/resume round trips it took to get there."""
    import json

    import kafkaf.core.skills.loop as loop_module

    replies = ["ACTION: fake_gated: a"] * loop_module.MAX_ITERATIONS
    brain = ScriptedBrain(replies)
    result = await run_skill_loop(
        brain, [{"role": "user", "content": "hi"}], session_id="s1", user_message="hi"
    )

    # Deny-and-resume repeatedly — each resume consumes exactly one more
    # generate() call/iteration, until the shared MAX_ITERATIONS budget
    # (not a fresh one per resume) is exhausted.
    for _ in range(loop_module.MAX_ITERATIONS):
        assert result.pending_approval is not None
        row = skills_store.claim_approval(result.pending_approval.approval_id, "denied")
        conversation = json.loads(row["conversation_json"])
        conversation.append({"role": "user", "content": "OBSERVATION: error: denied"})
        result = await resume_skill_loop(
            brain, conversation, row["iterations_used"], session_id="s1", user_message="hi", brain_spec=None
        )

    assert len(brain.seen_messages) == loop_module.MAX_ITERATIONS
    assert result.pending_approval is None
    assert "wasn't able to finish" in result.reply


@pytest.mark.asyncio
async def test_council_mode_auto_denies_approval_gated_skill(fake_gated_skill):
    brain = ScriptedBrain(["ACTION: fake_gated: do it", "FINAL ANSWER: skipped that"])
    result = await run_skill_loop(brain, [{"role": "user", "content": "hi"}], allow_pause=False)
    assert result.pending_approval is None
    assert result.reply == "skipped that"
    assert fake_gated_skill.run_calls == []
    assert "council mode" in brain.seen_messages[1][-1]["content"]


@pytest.mark.asyncio
async def test_manual_write_mode_blocks_approval_gated_skill_with_no_approval_row(monkeypatch, fake_gated_skill):
    monkeypatch.setattr("kafkaf.core.config.settings.write_skills_mode", "manual")
    brain = ScriptedBrain(["ACTION: fake_gated: do it", "FINAL ANSWER: blocked"])
    result = await run_skill_loop(
        brain, [{"role": "user", "content": "hi"}], session_id="s1", user_message="hi"
    )
    assert result.reply == "blocked"
    assert result.pending_approval is None
    assert fake_gated_skill.run_calls == []
    assert skills_store.list_approvals(status=None) == []
