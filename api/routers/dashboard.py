"""
Executive Overview routes. Reuse dashboard/data_prep.py's
build_command_center / build_catalog_sales_history_series exactly -- both
already have no Streamlit import and no business logic of their own, only
call through the orchestrator, so there is nothing to reimplement here.
"""

from fastapi import APIRouter, Depends

from api.dependencies import get_orchestrator
from dashboard.data_prep import build_catalog_sales_history_series, build_command_center

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary")
def get_dashboard_summary(days_ahead: int = 7, orchestrator=Depends(get_orchestrator)):
    return build_command_center(orchestrator, days_ahead=days_ahead)


@router.get("/sales-trend")
def get_sales_trend(orchestrator=Depends(get_orchestrator)):
    """Catalog-wide confirmed-coverage daily sales series. Returns an
    explicit `error` field (never raises) when unavailable, so the
    frontend can render an honest empty state rather than treat a 200
    with no data as a transport failure."""
    series, error = build_catalog_sales_history_series(orchestrator)
    if error or series.empty:
        return {"dates": [], "values": [], "error": error}
    return {
        "dates": [str(d.date()) for d in series.index],
        "values": [float(v) for v in series.values],
        "error": None,
    }
