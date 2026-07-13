import pytest

from kafkaf.core import council
from kafkaf.core.audit import store as audit_store
from kafkaf.core.brains.base import Brain
from kafkaf.core.memory import store as memory_store


@pytest.fixture(autouse=True)
def _isolated_audit_db(monkeypatch, tmp_path):
    # run_skill_loop logs every skill call to the audit store, so any test
    # that combines council mode with skills needs the table to exist.
    monkeypatch.setattr("kafkaf.core.config.settings.db_path", str(tmp_path / "test.db"))
    audit_store.init_db()
    yield


class FixedBrain(Brain):
    def __init__(self, name: str, reply: str):
        self.name = name
        self._reply = reply

    async def generate(self, messages: list[dict[str, str]]) -> str:
        return self._reply


class FailingBrain(Brain):
    name = "failing"

    async def generate(self, messages: list[dict[str, str]]) -> str:
        raise RuntimeError("boom")


class EchoSynthesizer(Brain):
    name = "synthesizer"

    async def generate(self, messages: list[dict[str, str]]) -> str:
        return messages[0]["content"]


class ScriptedToolBrain(Brain):
    """Uses the calculator tool once, then gives a final answer — for
    testing that council mode combines with skills mode per brain."""

    def __init__(self, name: str, expression: str, final: str):
        self.name = name
        self._expression = expression
        self._final = final
        self._calls = 0

    async def generate(self, messages: list[dict[str, str]]) -> str:
        self._calls += 1
        if self._calls == 1:
            return f"ACTION: calculator: {self._expression}"
        return f"FINAL ANSWER: {self._final}"


@pytest.mark.asyncio
async def test_council_chat_synthesizes_multiple_answers(monkeypatch):
    brains = {"a:1": FixedBrain("brain-a", "answer A"), "a:2": FixedBrain("brain-b", "answer B")}
    monkeypatch.setattr(council, "get_brain", lambda spec: brains[spec])

    result = await council.council_chat(
        [{"role": "user", "content": "hi"}], ["a:1", "a:2"], EchoSynthesizer()
    )
    assert "answer A" in result
    assert "answer B" in result


@pytest.mark.asyncio
async def test_council_chat_returns_lone_survivor_without_synthesis(monkeypatch):
    brains = {"a:1": FixedBrain("brain-a", "answer A"), "a:2": FailingBrain()}
    monkeypatch.setattr(council, "get_brain", lambda spec: brains[spec])

    result = await council.council_chat(
        [{"role": "user", "content": "hi"}], ["a:1", "a:2"], EchoSynthesizer()
    )
    assert result == "answer A"


@pytest.mark.asyncio
async def test_council_chat_all_fail_raises(monkeypatch):
    monkeypatch.setattr(council, "get_brain", lambda spec: FailingBrain())
    with pytest.raises(RuntimeError):
        await council.council_chat(
            [{"role": "user", "content": "hi"}], ["a:1", "a:2"], EchoSynthesizer()
        )


@pytest.mark.asyncio
async def test_council_chat_combines_with_skills(monkeypatch):
    brains = {
        "a:1": ScriptedToolBrain("brain-a", "2 + 2", "four"),
        "a:2": ScriptedToolBrain("brain-b", "3 + 3", "six"),
    }
    monkeypatch.setattr(council, "get_brain", lambda spec: brains[spec])

    result = await council.council_chat(
        [{"role": "user", "content": "do some math"}],
        ["a:1", "a:2"],
        EchoSynthesizer(),
        use_skills=True,
    )
    assert "four" in result
    assert "six" in result


@pytest.mark.asyncio
async def test_council_chat_without_skills_does_not_run_tools(monkeypatch):
    # Without use_skills, a brain returning an ACTION line is treated as a
    # plain (if odd-looking) final answer — the tool is never executed.
    brains = {
        "a:1": ScriptedToolBrain("brain-a", "2 + 2", "four"),
        "a:2": FixedBrain("brain-b", "answer B"),
    }
    monkeypatch.setattr(council, "get_brain", lambda spec: brains[spec])

    result = await council.council_chat(
        [{"role": "user", "content": "do some math"}], ["a:1", "a:2"], EchoSynthesizer()
    )
    assert "ACTION: calculator" in result
    assert "four" not in result


@pytest.mark.asyncio
async def test_handle_chat_council_mode(monkeypatch, tmp_path):
    monkeypatch.setattr("kafkaf.core.config.settings.db_path", str(tmp_path / "test.db"))
    memory_store.init_db()
    audit_store.init_db()

    brains = {"a:1": FixedBrain("brain-a", "answer A"), "a:2": FixedBrain("brain-b", "answer B")}
    monkeypatch.setattr(council, "get_brain", lambda spec: brains[spec])
    monkeypatch.setattr(council, "_default_brain", EchoSynthesizer())

    reply = await council.handle_chat("s1", "hello", council_brains=["a:1", "a:2"])
    assert "answer A" in reply
    assert "answer B" in reply

    history = memory_store.get_history("s1")
    assert [m["content"] for m in history] == ["hello", reply]
