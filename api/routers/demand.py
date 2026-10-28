"""
Thin proxy routes over DemandForecastEngine
(demand_forecasting_agent/forecasting_engine.py) via
orchestrator.svc.demand_engine. No calculation happens here.
"""

from fastapi import APIRouter, Depends

from api.dependencies import get_orchestrator
from dashboard.data_prep import build_sales_history_series

router = APIRouter(prefix="/demand", tags=["demand"])


@router.get("/top-forecasted")
def get_top_forecasted_products(horizon_days: int = 7, limit: int = 10, orchestrator=Depends(get_orchestrator)):
    return orchestrator.svc.demand_engine.get_top_forecasted_products(horizon_days=horizon_days, limit=limit)


@router.get("/spikes")
def get_demand_spikes(orchestrator=Depends(get_orchestrator)):
    return orchestrator.svc.demand_engine.detect_demand_spikes()


@router.get("/declines")
def get_demand_declines(orchestrator=Depends(get_orchestrator)):
    return orchestrator.svc.demand_engine.detect_declining_demand()


@router.get("/summary")
def get_demand_summary(sku: str | None = None, orchestrator=Depends(get_orchestrator)):
    return orchestrator.svc.demand_engine.get_demand_summary(sku=sku)


@router.get("/{sku}/forecast")
def forecast_demand(
    sku: str, horizon_days: int = 7, store_id: str | None = None, orchestrator=Depends(get_orchestrator)
):
    return orchestrator.svc.demand_engine.forecast_demand(sku, horizon_days=horizon_days, store_id=store_id)


@router.get("/{sku}/sales-history")
def get_sales_history(sku: str, orchestrator=Depends(get_orchestrator)):
    """Confirmed-coverage daily sales series for one SKU -- reuses
    dashboard/data_prep.py::build_sales_history_series exactly (the same
    function already backing the Streamlit Inventory & Demand page's
    history chart), rather than re-deriving the series here. Returns an
    explicit `error` field (never raises) when unavailable, matching
    GET /dashboard/sales-trend's shape so the frontend can render both
    with the same chart component."""
    series, error = build_sales_history_series(orchestrator, sku)
    if error or series.empty:
        return {"dates": [], "values": [], "error": error}
    return {
        "dates": [str(d.date()) for d in series.index],
        "values": [float(v) for v in series.values],
        "error": None,
    }


@router.get("/{sku}/compare-inventory")
def compare_forecast_with_inventory(
    sku: str, horizon_days: int = 7, orchestrator=Depends(get_orchestrator)
):
    return orchestrator.svc.demand_engine.compare_forecast_with_inventory(sku, horizon_days=horizon_days)
