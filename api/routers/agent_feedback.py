"""
Agent Feedback routes -- the human-facing half of the AI feedback loop.
Thin proxy over agent_feedback/store.py and agent_feedback/retuning.py; no
storage or retuning logic is reimplemented here.
"""

from fastapi import APIRouter
from pydantic import BaseModel

from agent_feedback import store
from agent_feedback.retuning import force_retune, maybe_retune
from agent_monitoring.registry import AGENT_BY_KEY, AGENT_REGISTRY

router = APIRouter(prefix="/agent-feedback", tags=["agent-feedback"])


class FeedbackSubmission(BaseModel):
    agent_keys: list[str]
    query: str
    answer: str | None = None
    rating: str
    comment: str | None = None


@router.post("/")
def submit_feedback(body: FeedbackSubmission):
    if body.rating not in ("up", "down"):
        raise ValueError(f"rating must be 'up' or 'down', got {body.rating!r}")
    unknown_keys = [k for k in body.agent_keys if k not in AGENT_BY_KEY]
    if unknown_keys:
        raise ValueError(f"Unknown agent_key(s): {unknown_keys}. Valid keys: {sorted(AGENT_BY_KEY)}")

    agent_keys, feedback_ids = store.submit_feedback(
        agent_keys=body.agent_keys, query=body.query, answer=body.answer,
        rating=body.rating, comment=body.comment,
    )

    retune_results = []
    if body.rating == "down":
        for agent_key in agent_keys:
            retune_result = maybe_retune(agent_key)
            if retune_result["retuned"]:
                retune_results.append(retune_result)

    return {"agent_keys": agent_keys, "feedback_ids": feedback_ids, "retuned": retune_results}


@router.get("/summary")
def get_feedback_summary():
    results = []
    for agent in AGENT_REGISTRY:
        stats = store.get_feedback_stats(agent["agent_key"])
        results.append({
            "agent_key": agent["agent_key"],
            "agent_name": agent["agent_name"],
            **stats,
        })
    return results


@router.get("/")
def list_feedback(agent_key: str | None = None, limit: int = 50):
    if agent_key is not None and agent_key not in AGENT_BY_KEY:
        raise ValueError(f"Unknown agent_key: {agent_key!r}. Valid keys: {sorted(AGENT_BY_KEY)}")
    return store.list_feedback(agent_key=agent_key, limit=limit)


@router.get("/adjustments")
def list_adjustments(agent_key: str | None = None, limit: int = 50):
    if agent_key is not None and agent_key not in AGENT_BY_KEY:
        raise ValueError(f"Unknown agent_key: {agent_key!r}. Valid keys: {sorted(AGENT_BY_KEY)}")
    return store.list_adjustments(agent_key=agent_key, limit=limit)


@router.post("/retune/{agent_key}")
def retune(agent_key: str):
    if agent_key not in AGENT_BY_KEY:
        raise ValueError(f"Unknown agent_key: {agent_key!r}. Valid keys: {sorted(AGENT_BY_KEY)}")
    return force_retune(agent_key)
