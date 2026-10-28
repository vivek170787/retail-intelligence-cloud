"""
Thin proxy routes over OrderFulfillmentEngine
(order_fulfillment_agent/fulfillment_engine.py) via
orchestrator.svc.fulfillment_engine. No calculation happens here.
"""

from fastapi import APIRouter, Depends

from api.dependencies import get_orchestrator

router = APIRouter(prefix="/fulfillment", tags=["fulfillment"])


@router.get("/at-risk")
def get_orders_at_risk(orchestrator=Depends(get_orchestrator)):
    return orchestrator.svc.fulfillment_engine.get_orders_at_risk()


@router.get("/due-today")
def get_orders_due_today(orchestrator=Depends(get_orchestrator)):
    return orchestrator.svc.fulfillment_engine.get_orders_due_today()


@router.get("/inventory-shortages")
def get_orders_with_inventory_shortages(orchestrator=Depends(get_orchestrator)):
    return orchestrator.svc.fulfillment_engine.get_orders_with_inventory_shortages()


@router.get("/priorities")
def get_fulfillment_priorities(limit: int = 10, orchestrator=Depends(get_orchestrator)):
    return orchestrator.svc.fulfillment_engine.get_fulfillment_priorities(limit=limit)


@router.get("/summary")
def get_fulfillment_risk_summary(orchestrator=Depends(get_orchestrator)):
    return orchestrator.svc.fulfillment_engine.get_fulfillment_risk_summary()


@router.get("/orders/{order_id}")
def analyze_order_fulfillment(order_id: str, orchestrator=Depends(get_orchestrator)):
    return orchestrator.svc.fulfillment_engine.analyze_order_fulfillment(order_id)


@router.get("/orders/{order_id}/alternatives")
def find_alternative_fulfillment_options(order_id: str, orchestrator=Depends(get_orchestrator)):
    return orchestrator.svc.fulfillment_engine.find_alternative_fulfillment_options(order_id)
