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
    from kafkaf.core.enrichment import store as enrichment_store

    monkeypatch.setattr("kafkaf.core.config.settings.db_path", str(tmp_path / "test.db"))
    memory_store.init_db()
    audit_store.init_db()
    enrichment_store.init_db()

    brains = {"a:1": FixedBrain("brain-a", "answer A"), "a:2": FixedBrain("brain-b", "answer B")}
    monkeypatch.setattr(council, "get_brain", lambda spec: brains[spec])
    monkeypatch.setattr(council, "_default_brain", EchoSynthesizer())

    outcome = await council.handle_chat("s1", "hello", council_brains=["a:1", "a:2"])
    assert outcome.pending_approval is None
    assert "answer A" in outcome.reply
    assert "answer B" in outcome.reply

    history = memory_store.get_history("s1")
    assert [m["content"] for m in history] == ["hello", outcome.reply]


class StreamingBrain(Brain):
    """A brain whose generate_stream yields real chunks, for testing
    council.stream_chat independently of OllamaBrain."""

    def __init__(self, name: str, chunks: list[str], fail_after: int | None = None):
        self.name = name
        self._chunks = chunks
        self._fail_after = fail_after

    async def generate(self, messages: list[dict[str, str]]) -> str:
        return "".join(self._chunks)

    async def generate_stream(self, messages: list[dict[str, str]]):
        for i, chunk in enumerate(self._chunks):
            if self._fail_after is not None and i >= self._fail_after:
                raise RuntimeError("stream broke")
            yield chunk


@pytest.fixture
def _memory_and_enrichment_db(monkeypatch, tmp_path):
    from kafkaf.core.enrichment import store as enrichment_store

    monkeypatch.setattr("kafkaf.core.config.settings.db_path", str(tmp_path / "test.db"))
    memory_store.init_db()
    audit_store.init_db()
    enrichment_store.init_db()
    yield


class TestBuildMessagesAndTaughtFacts:
    def test_no_facts_when_corpus_empty(self, _memory_and_enrichment_db):
        messages = council._build_messages("default", "s-empty", "tell me about kafkaf")
        assert "Relevant facts" not in messages[0]["content"]

    def test_injects_fact_matching_full_message(self, _memory_and_enrichment_db):
        from kafkaf.core.enrichment import service as enrichment_service

        enrichment_service.teach_fact("kafkaf", "kafkaf is a self-hosted AI platform")
        messages = council._build_messages("default", "s1", "kafkaf")
        assert "Relevant facts" in messages[0]["content"]
        assert "self-hosted AI platform" in messages[0]["content"]

    def test_falls_back_to_word_queries_when_full_message_misses(self, _memory_and_enrichment_db):
        from kafkaf.core.enrichment import service as enrichment_service

        # The full sentence never appears verbatim in the stored fact, but
        # "workspace" (a significant word in the message) does.
        enrichment_service.teach_fact("workspace", "the workspace directory is sandboxed")
        messages = council._build_messages(
            "default", "s1", "what directory does the workspace use for files?"
        )
        assert "Relevant facts" in messages[0]["content"]
        assert "sandboxed" in messages[0]["content"]

    def test_no_facts_for_unrelated_message(self, _memory_and_enrichment_db):
        from kafkaf.core.enrichment import service as enrichment_service

        enrichment_service.teach_fact("kafkaf", "kafkaf is a self-hosted AI platform")
        messages = council._build_messages("default", "s1", "what time is it")
        assert "Relevant facts" not in messages[0]["content"]


@pytest.mark.asyncio
async def test_handle_chat_and_stream_chat_share_build_messages(_memory_and_enrichment_db, monkeypatch):
    calls = []
    original = council._build_messages

    def spy(persona_key, session_id, message):
        calls.append((persona_key, session_id, message))
        return original(persona_key, session_id, message)

    monkeypatch.setattr(council, "_build_messages", spy)

    plain_brain = FixedBrain("plain", "a reply")
    stream_brain = StreamingBrain("stream", ["a ", "reply"])

    await council.handle_chat("s1", "hello there", brain=plain_brain)
    async for _ in council.stream_chat("s2", "hello there", brain=stream_brain):
        pass

    assert calls == [("default", "s1", "hello there"), ("default", "s2", "hello there")]


@pytest.mark.asyncio
async def test_stream_chat_happy_path_saves_history(_memory_and_enrichment_db):
    brain = StreamingBrain("stream", ["Hel", "lo!"])
    chunks = [chunk async for chunk in council.stream_chat("s-stream", "hi", brain=brain)]
    assert chunks == ["Hel", "lo!"]

    history = memory_store.get_history("s-stream")
    assert [m["content"] for m in history] == ["hi", "Hello!"]


@pytest.mark.asyncio
async def test_stream_chat_error_mid_stream_saves_no_history(_memory_and_enrichment_db):
    brain = StreamingBrain("stream", ["partial ", "never sent"], fail_after=1)
    with pytest.raises(RuntimeError):
        async for _ in council.stream_chat("s-fail", "hi", brain=brain):
            pass

    assert memory_store.get_history("s-fail") == []
