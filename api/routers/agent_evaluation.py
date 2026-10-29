"""
Agent Evaluation routes. Thin proxy over agent_evaluation/test_cases.py,
agent_evaluation/runner.py, and agent_evaluation/eval_log.py -- no scoring
logic is reimplemented here.
"""

from fastapi import APIRouter

from agent_evaluation import eval_log
from agent_evaluation.runner import run_evaluations
from agent_evaluation.test_cases import TEST_CASES
from agent_monitoring.registry import AGENT_BY_KEY, AGENT_REGISTRY

router = APIRouter(prefix="/agent-evaluation", tags=["agent-evaluation"])


@router.get("/test-cases")
def list_test_cases():
    return TEST_CASES


@router.post("/run")
def run(agent_key: str | None = None):
    if agent_key is not None and agent_key not in AGENT_BY_KEY:
        raise ValueError(f"Unknown agent_key: {agent_key!r}. Valid keys: {sorted(AGENT_BY_KEY)}")
    return run_evaluations(agent_key=agent_key)


@router.get("/results")
def get_results(agent_key: str | None = None, limit: int = 100):
    if agent_key is not None and agent_key not in AGENT_BY_KEY:
        raise ValueError(f"Unknown agent_key: {agent_key!r}. Valid keys: {sorted(AGENT_BY_KEY)}")
    return eval_log.list_results(agent_key=agent_key, limit=limit)


@router.get("/summary")
def get_summary():
    results = []
    for agent in AGENT_REGISTRY:
        summary = eval_log.get_summary(agent["agent_key"])
        results.append({
            "agent_key": agent["agent_key"],
            "agent_name": agent["agent_name"],
            **summary,
        })
    return results
