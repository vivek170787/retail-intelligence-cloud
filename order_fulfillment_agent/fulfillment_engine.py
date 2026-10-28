"""
Deterministic order fulfillment analysis for the Order Fulfillment
Intelligence Agent.

Dataset reality (confirmed by inspection, not assumed):
  - orders.csv has: order_id, customer_id, order_date, sku, quantity,
    order_status, fulfillment_location, promised_delivery_date. There is
    NO actual_delivery_date, shipment_status, tracking, or carrier field,
    and NO customer contact field. This agent never fabricates any of these.
  - fulfillment_location can be EITHER a store_id OR a warehouse_id (both
    appear in real data) -- this engine always checks which, rather than
    assuming one.
  - Each order row is a single SKU/quantity line; the dataset does not
    model true multi-line orders. Duplicate order_id rows (a data-quality
    issue, not a dataset feature) are handled defensively, not assumed away.
  - There is no outbound transit-time/carrier model between a fulfillment
    location and a customer. warehouse.csv's supplier_lead_time_days is an
    INBOUND replenishment lead time to the warehouse -- not the same thing
    -- and is labeled as such wherever it's surfaced here.

Because of the above, this agent explicitly separates:
  - inventory_readiness: can the assigned location's eligible stock cover
    the order today? (fully computable from the data)
  - delivery_feasibility: will it physically arrive by the promised date?
    (NOT computable -- no transit-time data exists -- always reported as
    "unknown" with the reason stated, never guessed)

risk_level is derived only from concrete evidence: whether the promised
date has already passed (a broken promise is a fact, not a prediction),
and inventory shortfall relative to time remaining. An order with a
future promised date and sufficient inventory is never escalated.

Reuses existing agents' public interfaces directly:
  - InventoryRiskEngine.get_product_inventory_analysis(sku) for store stock
  - InventoryRiskEngine.get_warehouse_availability(sku) for warehouse stock
  - DemandForecastEngine.forecast_demand(sku, horizon_days) -- only called
    when inventory is tight/insufficient, per "don't call agents unnecessarily"
  - promotion_agent.promotion_engine.promotion_status() (a pure function,
    no I/O) plus RetailDataService.get_promotions(sku) directly -- a
    lightweight overlap check, rather than invoking the full Promotion
    Intelligence Agent's heavier readiness computation (which would itself
    re-call the Inventory and Demand engines a second time)

All recommendations are read-only text for human review. This module never
changes an order status, reassigns a fulfillment location, transfers
stock, cancels an order, issues a refund, or sends any notification.
"""

import pandas as pd

from services.retail_data_service import RetailDataService
from inventory_agent.config import OPEN_ORDER_STATUSES
from inventory_agent.risk_engine import InventoryRiskEngine
from demand_forecasting_agent.forecasting_engine import DemandForecastEngine
from promotion_agent.promotion_engine import promotion_status as _promotion_status_fn
from order_fulfillment_agent.config import FulfillmentRiskSettings

RISK_CRITICAL = "critical"
RISK_HIGH = "high"
RISK_MEDIUM = "medium"
RISK_LOW = "low"
RISK_UNABLE_TO_ASSESS = "unable_to_assess"
RISK_NOT_APPLICABLE = "not_applicable"

RISK_SEVERITY_ORDER = {
    RISK_CRITICAL: 0, RISK_HIGH: 1, RISK_MEDIUM: 2,
    RISK_UNABLE_TO_ASSESS: 3, RISK_LOW: 4, RISK_NOT_APPLICABLE: 5,
}

DISCLAIMER = (
    "All recommendations are read-only and require human approval. This "
    "agent never changes an order status, reassigns a fulfillment location, "
    "transfers stock, cancels an order, issues a refund, or sends any "
    "customer communication."
)

DELIVERY_FEASIBILITY_REASON = (
    "This dataset has no shipment tracking, carrier information, actual "
    "delivery dates, or outbound transit-time data between a fulfillment "
    "location and the customer, so delivery feasibility beyond inventory "
    "readiness and the promised date cannot be assessed."
)


# --------------------------------------------------------------------- #
# Pure functions -- no I/O
# --------------------------------------------------------------------- #
def classify_order_risk(is_open, promised_missing, promised_passed, inventory_sufficient,
                         inventory_unknown, days_until_due, settings):
    """Risk level from concrete evidence only. A future promised date with
    sufficient inventory is always LOW -- never escalated on "not yet
    delivered" alone. An already-broken promise is CRITICAL regardless of
    inventory, since that is a fact, not a prediction."""
    if not is_open:
        return RISK_NOT_APPLICABLE
    if inventory_unknown:
        return RISK_UNABLE_TO_ASSESS
    if promised_passed:
        return RISK_CRITICAL
    if promised_missing:
        return RISK_UNABLE_TO_ASSESS
    if not inventory_sufficient:
        if days_until_due is not None and days_until_due <= settings.critical_days_until_due:
            return RISK_CRITICAL
        if days_until_due is not None and days_until_due <= settings.high_days_until_due:
            return RISK_HIGH
        return RISK_MEDIUM
    return RISK_LOW


def build_recommendations(risk_level, inventory_sufficient, alternatives_available):
    """Deterministic, read-only recommendation strings -- never an action."""
    recs = []
    if risk_level == RISK_CRITICAL:
        recs.append("Escalate for immediate human review -- promised date already passed or fulfillment is highly time-constrained.")
    if risk_level in (RISK_CRITICAL, RISK_HIGH) and not inventory_sufficient:
        recs.append("Investigate inventory shortage at the assigned fulfillment location before the promised date.")
        if alternatives_available:
            recs.append("Review alternative fulfillment candidates identified for this order.")
    if risk_level == RISK_MEDIUM and not inventory_sufficient:
        recs.append("Monitor inventory at the assigned location; there is time remaining but stock is currently short.")
    if risk_level == RISK_UNABLE_TO_ASSESS:
        recs.append("Review this order manually -- insufficient data (missing promised date, unknown inventory, or unrecognized fulfillment location) to assess automatically.")
    return recs


# --------------------------------------------------------------------- #
# Data-orchestration layer
# --------------------------------------------------------------------- #
class OrderFulfillmentEngine:
    def __init__(self, service=None, settings=None, inventory_engine=None, demand_engine=None):
        self.service = service if service is not None else RetailDataService()
        self.settings = settings if settings is not None else FulfillmentRiskSettings.from_env()
        self.inventory_engine = (
            inventory_engine if inventory_engine is not None
            else InventoryRiskEngine(service=self.service)
        )
        self.demand_engine = (
            demand_engine if demand_engine is not None
            else DemandForecastEngine(service=self.service, inventory_engine=self.inventory_engine)
        )
        # get_orders_at_risk() is the most expensive bulk scan here (every
        # open order) and is called repeatedly within a single request
        # (get_fulfillment_priorities(), the CX engine's get_customer_impact_risks(),
        # and the orchestrator's executive summary all call it independently).
        # Cached per resolved (normalized) reference_date -- see
        # InventoryRiskEngine._sku_analysis_cache for the same reasoning.
        self._orders_at_risk_cache = {}

    # ---- shared helpers -------------------------------------------------
    def _reference_date(self, reference_date=None):
        return pd.Timestamp(reference_date).normalize() if reference_date is not None else pd.Timestamp.now().normalize()

    def _get_order_by_id(self, order_id):
        """Looks up a single order from the existing bulk get_orders()
        accessor (no new RetailDataService method needed). Raises
        ValueError for empty/None input; returns None for a well-formed
        but nonexistent order_id, matching this project's established
        unknown-but-valid-key convention."""
        if not isinstance(order_id, str) or not order_id.strip():
            raise ValueError(f"order_id must be a non-empty string, got: {order_id!r}")
        order_id = order_id.strip()

        orders_df = self.service.get_orders()
        matches = orders_df[orders_df["order_id"] == order_id]
        if len(matches) == 0:
            return None, 0
        if len(matches) > 1:
            return matches.iloc[0].to_dict(), len(matches)
        return matches.iloc[0].to_dict(), 1

    def _eligible_inventory_at_location(self, sku, fulfillment_location):
        """Looks up eligible (already net-of-reserved) stock at the order's
        assigned location, correctly distinguishing a store from a
        warehouse rather than assuming one. Returns
        (eligible_available, location_type, data_limitation)."""
        if not isinstance(fulfillment_location, str) or not fulfillment_location.strip():
            return None, "unknown", "fulfillment_location is missing or invalid."

        inventory_analysis = self.inventory_engine.get_product_inventory_analysis(sku)
        store_match = next(
            (row for row in inventory_analysis["observed"]["store_breakdown"] if row["store_id"] == fulfillment_location),
            None,
        )
        if store_match is not None:
            return store_match["available_quantity"], "store", None

        warehouse_info = self.inventory_engine.get_warehouse_availability(sku)
        warehouse_match = next(
            (row for row in warehouse_info["by_warehouse"] if row["warehouse_id"] == fulfillment_location),
            None,
        )
        if warehouse_match is not None:
            return warehouse_match["available"], "warehouse", None

        return None, "unknown", (
            f"fulfillment_location {fulfillment_location!r} was not found in store or "
            f"warehouse inventory data for this SKU."
        )

    def _demand_context(self, sku, horizon_days):
        try:
            forecast = self.demand_engine.forecast_demand(sku, horizon_days=horizon_days)
        except ValueError as exc:
            return {"checked": True, "available": False, "reason": str(exc)}
        if not forecast["sufficient_data"]:
            return {"checked": True, "available": False, "reason": "insufficient sales history to forecast demand"}
        return {
            "checked": True, "available": True,
            "horizon_days": horizon_days,
            "forecast_total_demand": forecast["total_forecast_demand"],
        }

    def _promotion_context(self, sku, reference_date, promised_delivery_date):
        """Lightweight overlap check using RetailDataService directly (the
        same shared data access every agent uses) plus promotion_agent's
        own pure status function -- not the full Promotion Intelligence
        Agent readiness computation, which would re-invoke the Inventory
        and Demand engines a second time for no added benefit here."""
        promos = self.service.get_promotions(sku)
        if len(promos) == 0:
            return None

        window_end = promised_delivery_date if pd.notna(promised_delivery_date) else reference_date
        relevant = []
        for _, promo in promos.iterrows():
            status_value = _promotion_status_fn(promo["start_date"], promo["end_date"], reference_date)
            overlaps_relevant_window = promo["start_date"] <= window_end and promo["end_date"] >= reference_date
            if status_value in ("active", "upcoming") and overlaps_relevant_window:
                relevant.append({
                    "promotion_id": promo["promotion_id"],
                    "status": status_value,
                    "start_date": str(promo["start_date"].date()),
                    "end_date": str(promo["end_date"].date()),
                })
        if not relevant:
            return None
        return {
            "has_relevant_promotion": True,
            "promotions": relevant,
            "note": "A promotion overlaps this order's fulfillment window, which may be affecting available inventory for this SKU.",
        }

    def _analyze_order_row(self, order, reference_date, include_context=True):
        order_id = order["order_id"]
        sku = order["sku"]
        quantity = order["quantity"]
        status_value = order["order_status"]
        fulfillment_location = order["fulfillment_location"]
        promised_date = order.get("promised_delivery_date")

        is_open = status_value in OPEN_ORDER_STATUSES
        promised_missing = pd.isna(promised_date)
        promised_passed = (not promised_missing) and pd.Timestamp(promised_date) < reference_date
        days_until_due = None
        days_overdue = None
        if not promised_missing:
            delta = (pd.Timestamp(promised_date) - reference_date).days
            if delta >= 0:
                days_until_due = delta
            else:
                days_overdue = -delta

        eligible_available = None
        location_type = "unknown"
        inventory_limitation = None
        inventory_sufficient = None
        inventory_unknown = True

        if not pd.isna(quantity):
            eligible_available, location_type, inventory_limitation = self._eligible_inventory_at_location(
                sku, fulfillment_location
            )
            if eligible_available is not None:
                inventory_sufficient = eligible_available >= quantity
                inventory_unknown = False

        risk_level = classify_order_risk(
            is_open, promised_missing, promised_passed, inventory_sufficient, inventory_unknown,
            days_until_due, self.settings,
        )

        shortfall = (
            round(quantity - eligible_available, 2)
            if (eligible_available is not None and not pd.isna(quantity))
            else None
        )
        if shortfall is not None and shortfall < 0:
            shortfall = 0.0

        demand_context = None
        promotion_context = None
        if include_context and is_open and inventory_sufficient is False:
            demand_context = self._demand_context(sku, self.settings.demand_forecast_horizon_days)
            promotion_context = self._promotion_context(
                sku, reference_date, promised_date if not promised_missing else reference_date
            )

        result = {
            "order_id": order_id,
            "order_found": True,
            "customer_id": order.get("customer_id"),
            "sku": sku,
            "quantity": quantity,
            "order_status": status_value,
            "fulfillment_location": fulfillment_location,
            "fulfillment_location_type": location_type,
            "order_date": str(pd.Timestamp(order["order_date"]).date()) if pd.notna(order.get("order_date")) else None,
            "promised_delivery_date": str(pd.Timestamp(promised_date).date()) if not promised_missing else None,
            "is_open": is_open,
            "promised_date_missing": promised_missing,
            "promised_date_passed": promised_passed if not promised_missing else None,
            "days_overdue": days_overdue,
            "days_until_due": days_until_due,
            "inventory_readiness": {
                "eligible_available_at_location": eligible_available,
                "quantity_required": quantity,
                "sufficient": inventory_sufficient,
                "shortfall": shortfall,
                "data_limitation": inventory_limitation,
                "provisional": True,
                "provisional_reason": (
                    "Eligible stock is available_quantity (on-hand minus reserved) at the "
                    "assigned location; this dataset does not model a separate open-order "
                    "commitment ledger beyond what reserved_quantity already represents, so "
                    "this figure may not reflect every other order's claim on the same stock."
                ),
            },
            "delivery_feasibility": {
                "status": "unknown",
                "reason": DELIVERY_FEASIBILITY_REASON,
            },
            "risk_level": risk_level,
            "demand_context": demand_context,
            "promotion_context": promotion_context,
            "recommendations": build_recommendations(risk_level, bool(inventory_sufficient), False),
            "disclaimer": DISCLAIMER,
        }
        return result

    # ---- required public functions -------------------------------------
    def get_orders_at_risk(self, reference_date=None):
        """Open orders classified critical/high/medium/unable_to_assess
        (excludes low -- healthy -- and not_applicable -- terminal).
        Memoized per resolved reference_date (see __init__)."""
        reference_date = self._reference_date(reference_date)
        if reference_date in self._orders_at_risk_cache:
            return self._orders_at_risk_cache[reference_date]

        orders_df = self.service.get_orders()
        open_orders = orders_df[orders_df["order_status"].isin(OPEN_ORDER_STATUSES)]

        results = []
        for _, order in open_orders.iterrows():
            report = self._analyze_order_row(order.to_dict(), reference_date, include_context=False)
            if report["risk_level"] in (RISK_CRITICAL, RISK_HIGH, RISK_MEDIUM, RISK_UNABLE_TO_ASSESS):
                results.append(report)

        results.sort(key=lambda r: RISK_SEVERITY_ORDER.get(r["risk_level"], 99))
        self._orders_at_risk_cache[reference_date] = results
        return results

    def get_orders_due_today(self, reference_date=None):
        """Open orders due today OR already overdue -- both need
        attention today, not just an exact calendar match."""
        reference_date = self._reference_date(reference_date)
        orders_df = self.service.get_orders()
        open_orders = orders_df[orders_df["order_status"].isin(OPEN_ORDER_STATUSES)]
        due = open_orders[
            open_orders["promised_delivery_date"].notna()
            & (open_orders["promised_delivery_date"] <= reference_date)
        ]

        results = [self._analyze_order_row(o.to_dict(), reference_date, include_context=False) for _, o in due.iterrows()]
        results.sort(key=lambda r: RISK_SEVERITY_ORDER.get(r["risk_level"], 99))
        return results

    def get_orders_with_inventory_shortages(self, reference_date=None):
        """Open orders where eligible inventory at the assigned location
        is below the required quantity."""
        reference_date = self._reference_date(reference_date)
        orders_df = self.service.get_orders()
        open_orders = orders_df[orders_df["order_status"].isin(OPEN_ORDER_STATUSES)]

        results = []
        for _, order in open_orders.iterrows():
            report = self._analyze_order_row(order.to_dict(), reference_date, include_context=False)
            if report["inventory_readiness"]["sufficient"] is False:
                results.append(report)

        results.sort(key=lambda r: (r["inventory_readiness"]["shortfall"] is None, -(r["inventory_readiness"]["shortfall"] or 0)))
        return results

    def analyze_order_fulfillment(self, order_id, reference_date=None):
        """Full single-order deep dive: risk, inventory readiness,
        delivery feasibility (always "unknown" -- no data for it),
        relevant demand/promotion context, and alternative fulfillment
        candidates."""
        reference_date = self._reference_date(reference_date)
        order, match_count = self._get_order_by_id(order_id)

        if order is None:
            return {
                "order_id": order_id, "order_found": False,
                "note": f"No order found with order_id {order_id!r}.",
            }

        report = self._analyze_order_row(order, reference_date, include_context=True)
        if match_count > 1:
            report["data_quality_warning"] = (
                f"{match_count} rows share order_id {order_id!r} in the dataset "
                f"(duplicate order lines); the first row was used for this analysis."
            )

        if report["order_status"] in ("DELIVERED", "CANCELLED"):
            report["note"] = (
                f"This order is already {report['order_status']}; no forward-looking "
                f"fulfillment risk applies. This dataset has no actual_delivery_date "
                f"field, so whether a DELIVERED order arrived on time cannot be determined."
            )

        if report["risk_level"] in (RISK_CRITICAL, RISK_HIGH, RISK_MEDIUM):
            alternatives = self.find_alternative_fulfillment_options(order_id, reference_date=reference_date)
            report["alternative_fulfillment_options"] = alternatives["alternative_candidates"]
            report["recommendations"] = build_recommendations(
                report["risk_level"], bool(report["inventory_readiness"]["sufficient"]),
                any(c["sufficient_stock"] for c in alternatives["alternative_candidates"]),
            )

        return report

    def find_alternative_fulfillment_options(self, order_id, reference_date=None):
        """Other stores/warehouses that might fulfill this order. Every
        candidate is labeled a "candidate requiring validation" (never
        "feasible") when stock is sufficient, since this dataset has no
        outbound transit-time data -- per explicit instruction, timing
        gaps are never papered over with an assumption."""
        reference_date = self._reference_date(reference_date)
        order, _ = self._get_order_by_id(order_id)
        if order is None:
            return {"order_id": order_id, "order_found": False, "alternative_candidates": []}

        sku = order["sku"]
        quantity = order["quantity"]
        current_location = order["fulfillment_location"]

        inventory_analysis = self.inventory_engine.get_product_inventory_analysis(sku)
        warehouse_info = self.inventory_engine.get_warehouse_availability(sku)

        candidates = []
        for store_row in inventory_analysis["observed"]["store_breakdown"]:
            if store_row["store_id"] == current_location:
                continue
            sufficient = store_row["available_quantity"] >= quantity if not pd.isna(quantity) else None
            candidates.append({
                "location_id": store_row["store_id"], "location_type": "store",
                "eligible_available": store_row["available_quantity"],
                "quantity_required": quantity,
                "sufficient_stock": sufficient,
                "lead_time_known": False,
                "lead_time_days": None,
                "feasibility": "candidate_requires_validation" if sufficient else "insufficient_stock",
                "note": (
                    "No outbound transit-time data exists between stores and the customer "
                    "in this dataset; even a sufficient-stock candidate requires manual "
                    "validation before any reassignment."
                ) if sufficient else "Insufficient stock at this location for the required quantity.",
            })

        for wh_row in warehouse_info["by_warehouse"]:
            if wh_row["warehouse_id"] == current_location:
                continue
            sufficient = wh_row["available"] >= quantity if not pd.isna(quantity) else None
            candidates.append({
                "location_id": wh_row["warehouse_id"], "location_type": "warehouse",
                "eligible_available": wh_row["available"],
                "quantity_required": quantity,
                "sufficient_stock": sufficient,
                "lead_time_known": wh_row["supplier_lead_time_days"] is not None,
                "lead_time_days": wh_row["supplier_lead_time_days"],
                "feasibility": "candidate_requires_validation" if sufficient else "insufficient_stock",
                "note": (
                    "supplier_lead_time_days is this warehouse's INBOUND replenishment lead "
                    "time, not outbound transit time to the customer; manual validation is "
                    "still required before any reassignment."
                ) if sufficient else "Insufficient stock at this location for the required quantity.",
            })

        candidates.sort(key=lambda c: (not bool(c["sufficient_stock"]), -(c["eligible_available"] or 0)))
        return {
            "order_id": order_id, "order_found": True, "sku": sku,
            "quantity_required": quantity, "current_fulfillment_location": current_location,
            "alternative_candidates": candidates,
            "disclaimer": DISCLAIMER,
        }

    def get_fulfillment_risk_summary(self, reference_date=None):
        reference_date = self._reference_date(reference_date)
        orders_df = self.service.get_orders()
        open_orders = orders_df[orders_df["order_status"].isin(OPEN_ORDER_STATUSES)]

        risk_counts = {level: 0 for level in (RISK_CRITICAL, RISK_HIGH, RISK_MEDIUM, RISK_LOW, RISK_UNABLE_TO_ASSESS)}
        shortage_count = 0
        due_or_overdue_count = 0

        for _, order in open_orders.iterrows():
            report = self._analyze_order_row(order.to_dict(), reference_date, include_context=False)
            risk_counts[report["risk_level"]] = risk_counts.get(report["risk_level"], 0) + 1
            if report["inventory_readiness"]["sufficient"] is False:
                shortage_count += 1
            if report["promised_date_passed"] or report["days_until_due"] == 0:
                due_or_overdue_count += 1

        return {
            "data_as_of": str(reference_date.date()),
            "total_open_orders": len(open_orders),
            "risk_counts": risk_counts,
            "orders_with_inventory_shortages": shortage_count,
            "orders_due_today_or_overdue": due_or_overdue_count,
            "settings_used": self.settings.as_dict(),
        }

    def get_fulfillment_priorities(self, limit=10, reference_date=None):
        if not isinstance(limit, int) or isinstance(limit, bool) or limit <= 0:
            raise ValueError(f"limit must be a positive integer, got: {limit!r}")

        at_risk = self.get_orders_at_risk(reference_date=reference_date)
        prioritized = [r for r in at_risk if r["risk_level"] != RISK_UNABLE_TO_ASSESS]
        prioritized.sort(
            key=lambda r: (
                RISK_SEVERITY_ORDER.get(r["risk_level"], 99),
                r["days_overdue"] is None,
                -(r["days_overdue"] or 0),
                r["days_until_due"] if r["days_until_due"] is not None else 9999,
            )
        )
        return prioritized[:limit]


_default_engine = OrderFulfillmentEngine()


def get_orders_at_risk():
    return _default_engine.get_orders_at_risk()


def get_orders_due_today():
    return _default_engine.get_orders_due_today()


def get_orders_with_inventory_shortages():
    return _default_engine.get_orders_with_inventory_shortages()


def analyze_order_fulfillment(order_id):
    return _default_engine.analyze_order_fulfillment(order_id)


def find_alternative_fulfillment_options(order_id):
    return _default_engine.find_alternative_fulfillment_options(order_id)


def get_fulfillment_risk_summary():
    return _default_engine.get_fulfillment_risk_summary()


def get_fulfillment_priorities(limit=10):
    return _default_engine.get_fulfillment_priorities(limit=limit)
