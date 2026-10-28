"""
Thin proxy routes over CustomerExperienceEngine
(customer_experience_agent/cx_engine.py) via orchestrator.svc.cx_engine.
No calculation happens here.
"""

from fastapi import APIRouter, Depends

from api.dependencies import get_orchestrator

router = APIRouter(prefix="/customer-experience", tags=["customer-experience"])


@router.get("/impact-risks")
def get_customer_impact_risks(orchestrator=Depends(get_orchestrator)):
    return orchestrator.svc.cx_engine.get_customer_impact_risks()


@router.get("/at-risk")
def get_at_risk_customer_orders(limit: int = 10, orchestrator=Depends(get_orchestrator)):
    return orchestrator.svc.cx_engine.get_at_risk_customer_orders(limit=limit)


@router.get("/recovery-recommendations")
def get_service_recovery_recommendations(orchestrator=Depends(get_orchestrator)):
    return orchestrator.svc.cx_engine.get_service_recovery_recommendations()


@router.get("/summary")
def get_customer_experience_summary(orchestrator=Depends(get_orchestrator)):
    return orchestrator.svc.cx_engine.get_customer_experience_summary()


@router.get("/orders/{order_id}")
def analyze_customer_order_experience(order_id: str, orchestrator=Depends(get_orchestrator)):
    return orchestrator.svc.cx_engine.analyze_customer_order_experience(order_id)
