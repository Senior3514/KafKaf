import pytest

from kafkaf.core.memory import store as memory_store


@pytest.fixture(autouse=True)
def _isolated_db(monkeypatch, tmp_path):
    monkeypatch.setattr("kafkaf.core.config.settings.db_path", str(tmp_path / "test.db"))
    memory_store.init_db()
    yield


def test_get_history_uses_settings_history_window_by_default(monkeypatch):
    monkeypatch.setattr("kafkaf.core.config.settings.history_window", 4)
    for i in range(10):
        memory_store.save_message("s1", "user", f"msg-{i}")

    history = memory_store.get_history("s1")
    assert len(history) == 4
    assert [m["content"] for m in history] == ["msg-6", "msg-7", "msg-8", "msg-9"]


def test_get_history_explicit_limit_overrides_setting(monkeypatch):
    monkeypatch.setattr("kafkaf.core.config.settings.history_window", 4)
    for i in range(10):
        memory_store.save_message("s1", "user", f"msg-{i}")

    history = memory_store.get_history("s1", limit=2)
    assert [m["content"] for m in history] == ["msg-8", "msg-9"]
