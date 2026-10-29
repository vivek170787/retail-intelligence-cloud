"""
Tests for the Agent Evaluation API routes (api/routers/agent_evaluation.py).
Uses FastAPI's TestClient against the real app, same style as
tests/test_api.py. OPENAI_API_KEY is removed so judge scoring is
deterministically skipped, and eval_log's DB_PATH is monkeypatched to a
per-test tmp_path file so these tests never touch the project's real
db/agent_evaluation.db.
"""

from fastapi.testclient import TestClient

from agent_evaluation import eval_log
from agent_monitoring.registry import AGENT_REGISTRY
from api.main import app

client = TestClient(app)


def test_list_test_cases_covers_every_registered_agent():
    resp = client.get("/api/v1/agent-evaluation/test-cases")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) > 0
    assert {c["agent_key"] for c in body} <= {a["agent_key"] for a in AGENT_REGISTRY}


def test_run_for_unknown_agent_returns_400():
    resp = client.post("/api/v1/agent-evaluation/run", params={"agent_key": "not_a_real_agent"})
    assert resp.status_code == 400
    assert resp.json()["error"]["type"] == "invalid_request"


def test_run_and_fetch_results_for_one_agent(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(eval_log, "DB_PATH", tmp_path / "eval.db")

    run_resp = client.post("/api/v1/agent-evaluation/run", params={"agent_key": "demand"})
    assert run_resp.status_code == 200
    run_body = run_resp.json()
    assert len(run_body) == 2
    assert all(r["agent_key"] == "demand" for r in run_body)

    results_resp = client.get("/api/v1/agent-evaluation/results", params={"agent_key": "demand"})
    assert results_resp.status_code == 200
    assert len(results_resp.json()) == 2


def test_summary_lists_every_registered_agent(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(eval_log, "DB_PATH", tmp_path / "eval2.db")

    client.post("/api/v1/agent-evaluation/run", params={"agent_key": "promotion"})

    resp = client.get("/api/v1/agent-evaluation/summary")
    assert resp.status_code == 200
    body = resp.json()
    assert {a["agent_key"] for a in body} == {a["agent_key"] for a in AGENT_REGISTRY}

    promotion_row = next(a for a in body if a["agent_key"] == "promotion")
    assert promotion_row["total_runs"] == 2
    assert promotion_row["avg_judge_overall"] is None
