"""
Tests for the Agent Feedback API routes (api/routers/agent_feedback.py).
Uses FastAPI's TestClient against the real app, same style as
tests/test_api.py. agent_feedback.store's DB_PATH is monkeypatched to a
per-test tmp_path file so these tests never touch the project's real
db/agent_feedback.db.
"""

from fastapi.testclient import TestClient

from agent_feedback import store
from agent_feedback.retuning import NEGATIVE_FEEDBACK_THRESHOLD
from agent_monitoring.registry import AGENT_REGISTRY
from api.main import app

client = TestClient(app)


def test_submit_feedback_invalid_rating_returns_400(monkeypatch, tmp_path):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "feedback.db")

    resp = client.post(
        "/api/v1/agent-feedback/",
        json={"agent_keys": ["inventory"], "query": "q", "rating": "sideways"},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["type"] == "invalid_request"


def test_submit_feedback_unknown_agent_key_returns_400(monkeypatch, tmp_path):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "feedback2.db")

    resp = client.post(
        "/api/v1/agent-feedback/",
        json={"agent_keys": ["not_a_real_agent"], "query": "q", "rating": "up"},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["type"] == "invalid_request"


def test_submit_feedback_triggers_retune_at_threshold(monkeypatch, tmp_path):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "feedback3.db")

    last_resp = None
    for i in range(NEGATIVE_FEEDBACK_THRESHOLD):
        last_resp = client.post(
            "/api/v1/agent-feedback/",
            json={
                "agent_keys": ["inventory"],
                "query": f"q{i}",
                "answer": "a",
                "rating": "down",
                "comment": f"issue {i}",
            },
        )
        assert last_resp.status_code == 200

    body = last_resp.json()
    assert len(body["retuned"]) == 1
    assert body["retuned"][0]["agent_key"] == "inventory"
    assert body["retuned"][0]["retuned"] is True

    adjustments_resp = client.get("/api/v1/agent-feedback/adjustments", params={"agent_key": "inventory"})
    assert adjustments_resp.status_code == 200
    assert len(adjustments_resp.json()) == 1


def test_feedback_summary_lists_every_registered_agent(monkeypatch, tmp_path):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "feedback4.db")

    client.post(
        "/api/v1/agent-feedback/",
        json={"agent_keys": ["demand"], "query": "q", "answer": "a", "rating": "up"},
    )

    resp = client.get("/api/v1/agent-feedback/summary")
    assert resp.status_code == 200
    body = resp.json()
    assert {a["agent_key"] for a in body} == {a["agent_key"] for a in AGENT_REGISTRY}
    demand_row = next(a for a in body if a["agent_key"] == "demand")
    assert demand_row["up_count"] == 1
    assert demand_row["active_adjustment"] is None


def test_force_retune_endpoint(monkeypatch, tmp_path):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "feedback5.db")

    resp = client.post("/api/v1/agent-feedback/retune/customer_experience")
    assert resp.status_code == 200
    body = resp.json()
    assert body["retuned"] is True
    assert body["forced"] is True

    resp2 = client.post("/api/v1/agent-feedback/retune/not_a_real_agent")
    assert resp2.status_code == 400
