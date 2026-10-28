"""
RetailOrchestrationService: connects the Inventory Intelligence Agent, the
Demand Forecasting Agent, the Promotion Intelligence Agent, the Order
Fulfillment Intelligence Agent, and the Customer Experience Intelligence
Agent through direct Python function calls.

No OpenAI model is used to call any agent -- orchestration is plain
Python. (A separate, optional NL explanation layer lives in
orchestration/llm_explainer.py, mirroring each agent's own llm_explainer.py.)

Reuses each agent's existing public interface exactly as built:
  - InventoryRiskEngine.get_product_inventory_analysis(sku)   (inventory_agent/risk_engine.py)
  - DemandForecastEngine.forecast_demand(sku, horizon_days, store_id)  (demand_forecasting_agent/forecasting_engine.py)
  - PromotionIntelligenceEngine.get_promotion_readiness_report(...)  (promotion_agent/promotion_engine.py)
  - OrderFulfillmentEngine.analyze_order_fulfillment(order_id)  (order_fulfillment_agent/fulfillment_engine.py)
  - CustomerExperienceEngine.analyze_customer_order_experience(order_id)  (customer_experience_agent/cx_engine.py)
    -- each of these already combines the engines above internally where
    needed, so the orchestrator registers them rather than re-combining
    the same data a second time.

No agent's code is modified or duplicated. One RetailDataService instance
is shared across all five engines (and the orchestrator itself makes no
direct CSV/SQLite access of its own), so the data layer is loaded once,
not five times.
"""

from services.retail_data_service import RetailDataService
from inventory_agent.risk_engine import InventoryRiskEngine
from demand_forecasting_agent.forecasting_engine import DemandForecastEngine
from promotion_agent.promotion_engine import PromotionIntelligenceEngine
from order_fulfillment_agent.fulfillment_engine import OrderFulfillmentEngine
from customer_experience_agent.cx_engine import CustomerExperienceEngine

DISCLAIMER = (
    "demand_gap is a preliminary estimate for investigation only -- it is "
    "not a final replenishment decision, and no inventory, purchase order, "
    "or stock transfer is created automatically."
)


class RetailOrchestrationService:
    def __init__(self, service=None, inventory_engine=None, demand_engine=None,
                 promotion_engine=None, fulfillment_engine=None, cx_engine=None):
        self.service = service if service is not None else RetailDataService()
        self.inventory_engine = (
            inventory_engine if inventory_engine is not None
            else InventoryRiskEngine(service=self.service)
        )
        self.demand_engine = (
            demand_engine if demand_engine is not None
            else DemandForecastEngine(service=self.service, inventory_engine=self.inventory_engine)
        )
        self.promotion_engine = (
            promotion_engine if promotion_engine is not None
            else PromotionIntelligenceEngine(
                service=self.service, inventory_engine=self.inventory_engine, demand_engine=self.demand_engine
            )
        )
        self.fulfillment_engine = (
            fulfillment_engine if fulfillment_engine is not None
            else OrderFulfillmentEngine(
                service=self.service, inventory_engine=self.inventory_engine, demand_engine=self.demand_engine
            )
        )
        self.cx_engine = (
            cx_engine if cx_engine is not None
            else CustomerExperienceEngine(service=self.service, fulfillment_engine=self.fulfillment_engine)
        )

    def _validate_store_id(self, store_id):
        if store_id is None:
            return None
        if not isinstance(store_id, str) or not store_id.strip():
            raise ValueError(f"store_id must be a non-empty string, got: {store_id!r}")
        store_id = store_id.strip()
        stores_df = self.service.get_stores()
        if store_id not in set(stores_df["store_id"]):
            raise ValueError(
                f"Unknown store_id: {store_id!r}. Valid store_ids: {sorted(stores_df['store_id'])}"
            )
        return store_id

    def _store_matched_available(self, inventory_analysis, store_id, warnings):
        """Match current inventory to a specific store by store_id, rather
        than using the all-store combined total, when store_id is given."""
        if store_id is None:
            return inventory_analysis["observed"]["store_available_inventory"]

        breakdown = inventory_analysis["observed"]["store_breakdown"]
        match = next((row for row in breakdown if row["store_id"] == store_id), None)
        if match is None:
            warnings.append(
                f"No inventory record found for store {store_id!r} and SKU "
                f"{inventory_analysis['sku']!r}; treating current available "
                f"inventory as 0 rather than fabricating a figure."
            )
            return 0.0
        return match["available_quantity"]

    def _inbound_with_clear_timing(self, inventory_analysis, horizon_days, warnings):
        """Only count inbound stock toward the gap calculation when its
        expected arrival timing is actually known (supplier_lead_time_days
        is set) and clearly falls within the forecast horizon. Inbound
        stock with unknown or longer lead times is reported separately,
        never silently folded into the primary gap."""
        by_warehouse = inventory_analysis["observed"]["warehouse"]["by_warehouse"]
        total_inbound = inventory_analysis["observed"]["warehouse"]["warehouse_inbound"]

        if not by_warehouse:
            return 0.0, 0.0, total_inbound, True

        within_horizon = 0.0
        unclear_timing = 0.0
        has_clear_timing_row = False
        for row in by_warehouse:
            lead_time = row["supplier_lead_time_days"]
            if lead_time is not None and lead_time <= horizon_days:
                within_horizon += row["inbound_quantity"]
                has_clear_timing_row = True
            else:
                unclear_timing += row["inbound_quantity"]

        if unclear_timing > 0:
            warnings.append(
                f"{unclear_timing:g} unit(s) of inbound stock have an unknown or "
                f"longer-than-horizon supplier lead time and were excluded from "
                f"the gap-including-inbound figure rather than assumed to arrive in time."
            )

        return within_horizon, unclear_timing, total_inbound, has_clear_timing_row

    def _analyze_one(self, sku, horizon_days, store_id=None):
        """Core per-SKU[/store] combined analysis. Raises ValueError/other
        exceptions from either agent for truly invalid input (e.g. empty
        sku); well-formed-but-unknown SKUs are handled gracefully, matching
        both agents' own established convention."""
        forecast = self.demand_engine.forecast_demand(sku, horizon_days=horizon_days, store_id=store_id)
        inventory = self.inventory_engine.get_product_inventory_analysis(sku)

        sku_identifiers_matched = forecast["sku"] == inventory["sku"] == sku

        warnings = list(forecast["data_quality_warnings"])
        if not forecast["product_found"] or not inventory["product_found"]:
            warnings.append(f"SKU {sku!r} was not found in the product catalog.")
        if not sku_identifiers_matched:
            warnings.append(
                f"SKU identifier mismatch between agents: requested {sku!r}, "
                f"forecast returned {forecast['sku']!r}, inventory returned {inventory['sku']!r}."
            )

        current_available = self._store_matched_available(inventory, store_id, warnings)
        inbound_within_horizon, inbound_unclear, inbound_total, has_clear_timing_row = (
            self._inbound_with_clear_timing(inventory, horizon_days, warnings)
        )

        forecast_total = forecast["total_forecast_demand"]
        sufficient = forecast["sufficient_data"]

        demand_gap = None
        demand_gap_including_near_term_inbound = None
        if sufficient and forecast_total is not None:
            demand_gap = round(forecast_total - current_available, 2)
            if has_clear_timing_row:
                demand_gap_including_near_term_inbound = round(
                    forecast_total - (current_available + inbound_within_horizon), 2
                )
        else:
            warnings.append(
                "Forecast demand is unavailable (insufficient history); "
                "demand gap could not be calculated."
            )

        requires_investigation = bool(
            (demand_gap is not None and demand_gap > 0)
            or not sufficient
            or not forecast["product_found"]
            or not inventory["product_found"]
            or not sku_identifiers_matched
        )

        return {
            "sku": sku,
            "store_id": store_id,
            "product_name": forecast["product_name"] or (inventory["product"] or {}).get("product_name"),
            "horizon_days": horizon_days,
            "sku_identifiers_matched": sku_identifiers_matched,
            "forecast": {
                "total_demand": forecast_total,
                "method": forecast["forecast_method"],
                "sufficient_data": sufficient,
            },
            "inventory": {
                "current_available": current_available,
                "known_inbound_stock_total": inbound_total,
                "inbound_expected_within_horizon": inbound_within_horizon,
                "inbound_timing_unclear_amount": inbound_unclear,
                "inventory_agent_risk_level": inventory["estimated"]["risk_level"],
                "inventory_agent_suggested_replenishment_quantity": (
                    inventory["recommendation"]["suggested_replenishment_quantity"]
                ),
            },
            "demand_gap": demand_gap,
            "demand_gap_including_near_term_inbound": demand_gap_including_near_term_inbound,
            "requires_investigation": requires_investigation,
            "data_quality_warnings": warnings,
            "error": None,
            "disclaimer": DISCLAIMER,
        }

    def analyze_inventory_vs_forecast(self, sku=None, horizon_days=7, store_id=None):
        """Combined inventory-vs-forecast analysis.

        sku=None analyzes every product in the catalog (optionally scoped
        to one store via store_id); a specific sku analyzes just that
        product. Never duplicates either agent's own data access or
        calculations -- forecasting stays in DemandForecastEngine,
        inventory risk/replenishment stays in InventoryRiskEngine; this
        service only matches and compares their existing outputs.
        """
        if not isinstance(horizon_days, int) or isinstance(horizon_days, bool) or horizon_days <= 0:
            raise ValueError(f"horizon_days must be a positive integer, got: {horizon_days!r}")

        store_id = self._validate_store_id(store_id)

        if sku is not None:
            return self._analyze_one(sku, horizon_days, store_id=store_id)

        products_df = self.service.get_products()
        results = []
        for one_sku in products_df["sku"]:
            try:
                results.append(self._analyze_one(one_sku, horizon_days, store_id=store_id))
            except Exception as exc:
                # A single failing SKU (e.g. an unexpected error from either
                # agent) must not abort analysis of the rest of the catalog.
                results.append({
                    "sku": one_sku,
                    "store_id": store_id,
                    "error": f"{type(exc).__name__}: {exc}",
                    "requires_investigation": True,
                    "data_quality_warnings": [f"Unexpected error analyzing {one_sku!r}: {exc}"],
                })

        needing_investigation = [r for r in results if r.get("requires_investigation")]
        return {
            "scope": "catalog" if store_id is None else f"store:{store_id}",
            "horizon_days": horizon_days,
            "total_products_analyzed": len(results),
            "products_requiring_investigation": len(needing_investigation),
            "results": results,
        }


_default_orchestrator = RetailOrchestrationService()


def analyze_inventory_vs_forecast(sku=None, horizon_days=7, store_id=None):
    return _default_orchestrator.analyze_inventory_vs_forecast(
        sku=sku, horizon_days=horizon_days, store_id=store_id
    )
