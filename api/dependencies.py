"""
Shared FastAPI dependency: one cached RetailIntelligenceOrchestrator for the
whole API process, mirroring dashboard/state.py's @st.cache_resource pattern
-- the CSVs load once and every agent engine is built once, never per request.
"""

from functools import lru_cache

from orchestration.query_orchestrator import RetailIntelligenceOrchestrator


@lru_cache
def _orchestrator_singleton():
    return RetailIntelligenceOrchestrator()


def get_orchestrator():
    return _orchestrator_singleton()
