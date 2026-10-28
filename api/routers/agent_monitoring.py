"""
Agent Monitoring routes. Combines the static agent registry
(agent_monitoring/registry.py) with REAL, locally-logged execution records
(agent_monitoring/execution_log.py -- every row is an actual HTTP request
this backend served, written by api/main.py's logging middleware). No
execution data is fabricated or simulated here or anywhere in this module.
"""

from fastapi import APIRouter

from agent_monitoring.execution_log import get_agent_stats, list_executions
from agent_monitoring.registry import AGENT_BY_KEY, AGENT_REGISTRY

router = APIRouter(prefix="/agent-monitoring", tags=["agent-monitoring"])


def _status_for(stats):
    if stats["total_runs"] == 0:
        return "no_executions_recorded"
    return "healthy" if stats["last_execution"]["success"] else "error"


@router.get("/agents")
def list_agents():
    results = []
    for agent in AGENT_REGISTRY:
        stats = get_agent_stats(agent["agent_key"])
        results.append({
            **agent,
            "status": _status_for(stats),
            "total_runs": stats["total_runs"],
            "successful_runs": stats["successful_runs"],
            "failed_runs": stats["failed_runs"],
            "last_execution": stats["last_execution"],
        })
    return results


@router.get("/agents/{agent_key}/executions")
def get_agent_executions(agent_key: str, limit: int = 50):
    if agent_key not in AGENT_BY_KEY:
        raise ValueError(f"Unknown agent_key: {agent_key!r}. Valid keys: {sorted(AGENT_BY_KEY)}")
    return list_executions(agent_key=agent_key, limit=limit)


@router.get("/executions")
def get_all_executions(limit: int = 100):
    """Combined, chronological (most-recent-first) feed across every
    monitored agent -- backs the Agent Execution History workspace."""
    return list_executions(agent_key=None, limit=limit)
