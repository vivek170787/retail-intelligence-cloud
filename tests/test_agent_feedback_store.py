"""
Tests for agent_feedback/store.py. DB_PATH is monkeypatched to a per-test
tmp_path file so these tests never touch the project's real
db/agent_feedback.db.
"""

import pytest

from agent_feedback import store


def test_submit_feedback_fans_out_and_dedupes(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "feedback.db")

    agent_keys, ids = store.submit_feedback(
        agent_keys=["inventory", "demand", "inventory"],
        query="Which products need replenishment?",
        answer="Some answer text",
        rating="down",
        comment="not great",
    )

    assert agent_keys == ["inventory", "demand"]
    assert len(ids) == 2

    rows = store.list_feedback()
    assert len(rows) == 2
    assert {r["agent_key"] for r in rows} == {"inventory", "demand"}
    assert all(r["rating"] == "down" for r in rows)
    assert all(r["counted_in_adjustment_id"] is None for r in rows)


def test_submit_feedback_rejects_invalid_rating(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "feedback2.db")
    with pytest.raises(ValueError):
        store.submit_feedback(agent_keys=["inventory"], query="q", answer="a", rating="sideways")


def test_submit_feedback_falls_back_to_orchestrator_when_no_agent_keys(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "feedback3.db")
    agent_keys, ids = store.submit_feedback(agent_keys=[], query="q", answer="a", rating="up")
    assert agent_keys == ["orchestrator"]
    assert len(ids) == 1


def test_get_active_adjustment_none_then_set_after_create(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "feedback4.db")

    assert store.get_active_adjustment("inventory") is None

    adjustment_id = store.create_adjustment(
        agent_key="inventory", adjustment_text="be careful", trigger_feedback_count=0, feedback_ids_to_mark=[]
    )
    assert store.get_active_adjustment("inventory") == "be careful"

    adjustments = store.list_adjustments(agent_key="inventory")
    assert len(adjustments) == 1
    assert adjustments[0]["id"] == adjustment_id


def test_get_active_adjustment_returns_most_recent(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "feedback5.db")

    store.create_adjustment(agent_key="inventory", adjustment_text="first", trigger_feedback_count=0,
                             feedback_ids_to_mark=[])
    store.create_adjustment(agent_key="inventory", adjustment_text="second", trigger_feedback_count=0,
                             feedback_ids_to_mark=[])

    assert store.get_active_adjustment("inventory") == "second"


def test_create_adjustment_marks_feedback_rows_as_counted(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "feedback6.db")

    store.submit_feedback(agent_keys=["inventory"], query="q", answer="a", rating="down", comment="bad")
    uncounted = store.list_uncounted_negative_feedback("inventory")
    assert len(uncounted) == 1

    store.create_adjustment(
        agent_key="inventory", adjustment_text="note", trigger_feedback_count=1,
        feedback_ids_to_mark=[row["id"] for row in uncounted],
    )

    assert store.list_uncounted_negative_feedback("inventory") == []


def test_get_feedback_stats(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "feedback7.db")

    store.submit_feedback(agent_keys=["inventory"], query="q1", answer="a", rating="up")
    store.submit_feedback(agent_keys=["inventory"], query="q2", answer="a", rating="down", comment="bad")

    stats = store.get_feedback_stats("inventory")
    assert stats["total"] == 2
    assert stats["up_count"] == 1
    assert stats["down_count"] == 1
    assert stats["active_adjustment"] is None
