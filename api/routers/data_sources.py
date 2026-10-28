"""
Thin proxy route over data_sources/registry.py. No calculation happens here.
"""

from fastapi import APIRouter, Depends

from api.dependencies import get_orchestrator
from data_sources.registry import get_data_sources_overview

router = APIRouter(prefix="/data-sources", tags=["data-sources"])


@router.get("/overview")
def get_data_sources_overview_route(orchestrator=Depends(get_orchestrator)):
    # Reuses the shared, cached RetailDataService (orchestrator.svc.service
    # -- see orchestration/service.py and api/dependencies.py) rather than
    # re-reading every CSV file from disk on each call.
    return get_data_sources_overview(service=orchestrator.svc.service)
