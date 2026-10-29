"""
Tests for agent_evaluation/runner.py. Runs the REAL agent code (same
answer_question()/handle_query() path each agent's own cli.py uses) against
the hardcoded test_cases.py questions, with OPENAI_API_KEY removed from the
environment so these tests are fast, free, and deterministic -- matching
the project's existing "deterministic core works with no key" test
convention (see e.g. test_fulfillment_engine.py::
test_answer_question_works_without_api_key). eval_log's DB_PATH is
monkeypatched to a per-test tmp_path file so these tests never touch the
project's real db/agent_evaluation.db.
"""

from agent_evaluation import eval_log, runner


def test_run_evaluations_inventory_without_openai_key(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(eval_log, "DB_PATH", tmp_path / "eval.db")

    results = runner.run_evaluations(agent_key="inventory")

    assert len(results) == 2
    for result in results:
        assert result["agent_key"] == "inventory"
        assert result["status"] == "skipped_no_answer"
        assert result["judged"] is False
        assert result["evidence_passed"] is True
        assert result["missing_evidence_keys"] == []
        assert result["keyword_passed"] is True
        assert result["passed"] is True

    stored = eval_log.list_results(agent_key="inventory")
    assert len(stored) == 2
    assert {r["test_case_id"] for r in stored} == {"inventory_top_risks", "inventory_replenishment"}


def test_run_evaluations_orchestrator_without_openai_key(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(eval_log, "DB_PATH", tmp_path / "eval2.db")

    results = runner.run_evaluations(agent_key="orchestrator")

    assert len(results) == 2
    for result in results:
        assert result["agent_key"] == "orchestrator"
        assert result["evidence_passed"] is True
        assert result["passed"] is True


def test_run_evaluations_all_agents_without_openai_key(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(eval_log, "DB_PATH", tmp_path / "eval3.db")

    results = runner.run_evaluations()

    from agent_evaluation.test_cases import TEST_CASES

    assert len(results) == len(TEST_CASES)
    run_ids = {r["run_id"] for r in results}
    assert len(run_ids) == 1, "every test case in one run_evaluations() call should share one run_id"

    summary = eval_log.get_summary("inventory")
    assert summary["total_runs"] == 2
    assert summary["passed"] == 2
    assert summary["avg_judge_overall"] is None


def test_run_evaluations_detects_missing_evidence(monkeypatch, tmp_path):
    """A test case whose expected_evidence_keys don't exist in the real
    evidence must be reported as a failure, not silently passed."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(eval_log, "DB_PATH", tmp_path / "eval4.db")
    monkeypatch.setattr(
        runner,
        "TEST_CASES_BY_AGENT",
        {
            "inventory": [
                {
                    "id": "bad_case",
                    "agent_key": "inventory",
                    "question": "What are the top stockout risks right now?",
                    "expected_evidence_keys": ["summary", "this_key_does_not_exist"],
                    "answer_keywords_any": [],
                }
            ]
        },
    )

    results = runner.run_evaluations(agent_key="inventory")
    assert len(results) == 1
    assert results[0]["evidence_passed"] is False
    assert results[0]["missing_evidence_keys"] == ["this_key_does_not_exist"]
    assert results[0]["passed"] is False
