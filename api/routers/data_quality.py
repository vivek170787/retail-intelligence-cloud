"""
Thin proxy route over data_quality/report.py. No calculation happens here.
"""

from fastapi import APIRouter, Depends

from api.dependencies import get_orchestrator
from data_quality.report import build_quality_report

router = APIRouter(prefix="/data-quality", tags=["data-quality"])


@router.get("/report")
def get_data_quality_report(orchestrator=Depends(get_orchestrator)):
    # Reuses the shared, cached RetailDataService (orchestrator.svc.service
    # -- see orchestration/service.py and api/dependencies.py) rather than
    # re-reading every CSV file from disk on each call.
    return build_quality_report(service=orchestrator.svc.service)
