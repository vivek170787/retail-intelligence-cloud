"""
Thin proxy routes over InventoryRiskEngine (inventory_agent/risk_engine.py)
via orchestrator.svc.inventory_engine. No calculation happens here.

Static-path routes are declared before the "/{sku}" catch-all so they are
matched first (Starlette resolves routes in declaration order).
"""

from fastapi import APIRouter, Depends

from api.dependencies import get_orchestrator

router = APIRouter(prefix="/inventory", tags=["inventory"])


@router.get("/risks")
def get_inventory_risks(orchestrator=Depends(get_orchestrator)):
    return orchestrator.svc.inventory_engine.get_inventory_risks()


@router.get("/summary")
def get_inventory_summary(orchestrator=Depends(get_orchestrator)):
    return orchestrator.svc.inventory_engine.get_inventory_summary()


@router.get("/top-stockout-risks")
def get_top_stockout_risks(limit: int = 10, orchestrator=Depends(get_orchestrator)):
    return orchestrator.svc.inventory_engine.get_top_stockout_risks(limit=limit)


@router.get("/replenishment")
def get_replenishment_recommendations(orchestrator=Depends(get_orchestrator)):
    return orchestrator.svc.inventory_engine.get_replenishment_recommendations()


@router.get("/stores/{store_id}")
def get_store_inventory_risks(store_id: str, orchestrator=Depends(get_orchestrator)):
    return orchestrator.svc.inventory_engine.get_store_inventory_risks(store_id=store_id)


@router.get("/{sku}/warehouse")
def get_warehouse_availability(sku: str, orchestrator=Depends(get_orchestrator)):
    return orchestrator.svc.inventory_engine.get_warehouse_availability(sku)


@router.get("/{sku}")
def get_product_inventory_analysis(sku: str, orchestrator=Depends(get_orchestrator)):
    return orchestrator.svc.inventory_engine.get_product_inventory_analysis(sku)
