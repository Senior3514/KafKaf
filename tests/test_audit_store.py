import pytest

from kafkaf.core.audit import store


@pytest.fixture(autouse=True)
def _isolated_db(monkeypatch, tmp_path):
    monkeypatch.setattr("kafkaf.core.config.settings.db_path", str(tmp_path / "test.db"))
    store.init_db()
    yield


def test_log_and_recent_events_round_trip():
    store.log_event("chat", "ollama:llama3", "session=s1 msg_chars=5 reply_chars=10", 42)
    events = store.recent_events()
    assert len(events) == 1
    assert events[0]["event_type"] == "chat"
    assert events[0]["actor"] == "ollama:llama3"
    assert events[0]["duration_ms"] == 42


def test_recent_events_orders_newest_first():
    store.log_event("chat", "a", "first")
    store.log_event("chat", "b", "second")
    events = store.recent_events()
    assert [e["actor"] for e in events] == ["b", "a"]


def test_recent_events_respects_limit():
    for i in range(5):
        store.log_event("chat", str(i), "msg")
    events = store.recent_events(limit=2)
    assert len(events) == 2


def test_recent_events_filters_by_event_type():
    store.log_event("chat", "a", "chat event")
    store.log_event("skill", "calculator", "skill event")
    events = store.recent_events(event_type="skill")
    assert len(events) == 1
    assert events[0]["event_type"] == "skill"


def test_summary_truncated_at_max_chars():
    long_summary = "x" * (store.MAX_SUMMARY_CHARS + 100)
    store.log_event("chat", "a", long_summary)
    events = store.recent_events()
    assert len(events[0]["summary"]) == store.MAX_SUMMARY_CHARS + len("... [truncated]")


def test_actor_can_be_none():
    store.log_event("autopilot_stop", None, "stop file seen")
    events = store.recent_events()
    assert events[0]["actor"] is None
