"""
Tests for agent_feedback/retuning.py -- the automatic half of the AI
feedback loop. store.DB_PATH is monkeypatched to a per-test tmp_path file
(retuning.py imports its storage functions by name from agent_feedback.store,
but those functions read store.DB_PATH as a module global at call time, so
patching it on the store module affects them too).
"""

from agent_feedback import retuning, store


def test_maybe_retune_below_threshold_does_not_write(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "feedback.db")

    store.submit_feedback(agent_keys=["inventory"], query="q1", answer="a", rating="down", comment="c1")
    store.submit_feedback(agent_keys=["inventory"], query="q2", answer="a", rating="down", comment="c2")

    result = retuning.maybe_retune("inventory")
    assert result["retuned"] is False
    assert result["reason"] == "threshold_not_met"
    assert result["uncounted_negative_count"] == 2
    assert store.get_active_adjustment("inventory") is None


def test_maybe_retune_triggers_at_threshold_with_comments(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "feedback2.db")

    for i in range(retuning.NEGATIVE_FEEDBACK_THRESHOLD):
        store.submit_feedback(
            agent_keys=["inventory"], query=f"q{i}", answer="a", rating="down", comment=f"issue {i}"
        )

    result = retuning.maybe_retune("inventory")
    assert result["retuned"] is True
    assert result["trigger_feedback_count"] == retuning.NEGATIVE_FEEDBACK_THRESHOLD
    for i in range(retuning.NEGATIVE_FEEDBACK_THRESHOLD):
        assert f"issue {i}" in result["adjustment_text"]
    assert store.get_active_adjustment("inventory") == result["adjustment_text"]


def test_maybe_retune_does_not_double_count_already_counted_feedback(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "feedback3.db")

    for i in range(retuning.NEGATIVE_FEEDBACK_THRESHOLD):
        store.submit_feedback(agent_keys=["inventory"], query=f"q{i}", answer="a", rating="down", comment=f"c{i}")

    first = retuning.maybe_retune("inventory")
    assert first["retuned"] is True

    second = retuning.maybe_retune("inventory")
    assert second["retuned"] is False
    assert second["uncounted_negative_count"] == 0


def test_maybe_retune_only_retunes_requested_agent(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "feedback4.db")

    for i in range(retuning.NEGATIVE_FEEDBACK_THRESHOLD):
        store.submit_feedback(agent_keys=["inventory"], query=f"q{i}", answer="a", rating="down", comment=f"c{i}")

    retuning.maybe_retune("demand")
    assert store.get_active_adjustment("demand") is None
    assert store.get_active_adjustment("inventory") is None  # not yet triggered for inventory either


def test_force_retune_with_no_feedback_uses_generic_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "feedback5.db")

    result = retuning.force_retune("inventory")
    assert result["retuned"] is True
    assert result["forced"] is True
    assert result["trigger_feedback_count"] == 0
    assert "unhelpful or incorrect" in result["adjustment_text"]
    assert store.get_active_adjustment("inventory") == result["adjustment_text"]


def test_force_retune_below_threshold_still_fires(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "feedback6.db")

    store.submit_feedback(agent_keys=["inventory"], query="q1", answer="a", rating="down", comment="only one")

    result = retuning.force_retune("inventory")
    assert result["retuned"] is True
    assert result["trigger_feedback_count"] == 1
    assert "only one" in result["adjustment_text"]
