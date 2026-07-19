import pytest

from kafkaf.core.skills import store as skills_store


@pytest.fixture(autouse=True)
def _isolated_storage(monkeypatch, tmp_path):
    monkeypatch.setattr("kafkaf.core.config.settings.db_path", str(tmp_path / "test.db"))
    skills_store.init_db()
    yield


def test_add_and_get_approval():
    approval_id = skills_store.add_approval(
        "session-1", "do the thing", "ollama:llama3", "run_code", "print(1)", '[{"role": "user", "content": "hi"}]', 1
    )
    row = skills_store.get_approval(approval_id)
    assert row["id"] == approval_id
    assert row["session_id"] == "session-1"
    assert row["user_message"] == "do the thing"
    assert row["brain_spec"] == "ollama:llama3"
    assert row["skill_name"] == "run_code"
    assert row["skill_arg"] == "print(1)"
    assert row["iterations_used"] == 1
    assert row["status"] == "pending"
    assert row["decided_at"] is None


def test_get_nonexistent_returns_none():
    assert skills_store.get_approval(999) is None


def test_list_approvals_defaults_to_pending_only():
    id1 = skills_store.add_approval("s1", "m1", None, "run_code", "a", "[]", 0)
    id2 = skills_store.add_approval("s1", "m2", None, "run_code", "b", "[]", 0)
    skills_store.claim_approval(id2, "approved")

    pending = skills_store.list_approvals()
    assert [row["id"] for row in pending] == [id1]

    everything = skills_store.list_approvals(status=None)
    assert {row["id"] for row in everything} == {id1, id2}


def test_claim_approval_transitions_exactly_once():
    approval_id = skills_store.add_approval("s1", "m", None, "run_code", "a", "[]", 0)

    claimed = skills_store.claim_approval(approval_id, "approved")
    assert claimed is not None
    assert claimed["status"] == "pending"  # pre-decision snapshot returned

    row = skills_store.get_approval(approval_id)
    assert row["status"] == "approved"
    assert row["decided_at"] is not None

    # A second claim on the same (now-decided) row must not succeed —
    # this is what makes a double-click or a race between two tabs safe.
    second = skills_store.claim_approval(approval_id, "denied")
    assert second is None
    assert skills_store.get_approval(approval_id)["status"] == "approved"  # unchanged


def test_claim_approval_nonexistent_returns_none():
    assert skills_store.claim_approval(999, "approved") is None
