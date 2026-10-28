"""
Thin proxy routes over PromotionIntelligenceEngine
(promotion_agent/promotion_engine.py) via orchestrator.svc.promotion_engine.
No calculation happens here.
"""

from fastapi import APIRouter, Depends

from api.dependencies import get_orchestrator

router = APIRouter(prefix="/promotions", tags=["promotions"])


@router.get("/upcoming")
def get_upcoming_promotions(days_ahead: int = 14, orchestrator=Depends(get_orchestrator)):
    return orchestrator.svc.promotion_engine.get_upcoming_promotions(days_ahead=days_ahead)


@router.get("/readiness")
def get_promotion_readiness_report(days_ahead: int | None = None, orchestrator=Depends(get_orchestrator)):
    return orchestrator.svc.promotion_engine.get_promotion_readiness_report(days_ahead=days_ahead)


@router.get("/stockout-risks")
def get_promotion_stockout_risks(orchestrator=Depends(get_orchestrator)):
    return orchestrator.svc.promotion_engine.get_promotion_stockout_risks()


@router.get("/demand-summary")
def get_promotional_demand_summary(orchestrator=Depends(get_orchestrator)):
    return orchestrator.svc.promotion_engine.get_promotional_demand_summary()


@router.get("/{sku}")
def analyze_promotion_for_sku(sku: str, orchestrator=Depends(get_orchestrator)):
    return orchestrator.svc.promotion_engine.analyze_promotion_for_sku(sku)
