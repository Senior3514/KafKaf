from kafkaf.core.config import Settings


def test_history_window_default():
    assert Settings().history_window == 60


def test_history_window_env_override(monkeypatch):
    monkeypatch.setenv("KAFKAF_HISTORY_WINDOW", "10")
    assert Settings().history_window == 10
