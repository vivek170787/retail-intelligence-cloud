"""
Customer Experience Intelligence Agent.

This agent does NOT re-derive fulfillment, inventory, demand, or promotion
logic -- it is a thin layer over OrderFulfillmentEngine.analyze_order_fulfillment(),
which already combines InventoryRiskEngine and (conditionally)
DemandForecastEngine/PromotionIntelligenceEngine. This agent adds:
  - a confirmed-vs-predicted problem distinction,
  - a plain-language explanation built from the already-computed evidence,
  - marketplace listing-availability context (NEW: not checked by any
    other agent -- via RetailDataService.get_marketplace_listings(sku)),
  - a conservative, rule-based "potential cancellation risk" flag,
  - read-only service-recovery recommendation text.

No new inventory/forecast/promotion computation happens here. severity
reuses OrderFulfillmentEngine's own risk_level vocabulary verbatim rather
than inventing a second taxonomy.

Explicitly NOT supported by this dataset, and never fabricated:
  - "alternative product" recommendations -- there is no product
    substitutability/similarity mapping in products.csv (only sku,
    product_name, category, brand, selling_price, cost_price), so this
    is always reported unavailable with the reason stated, not guessed
    from category/brand similarity.
  - a policy-grounded specific recovery action (discount, expedite, etc.)
    -- there is no compensation/policy dataset in this project, so this
    agent only flags that a human-reviewed action MAY be warranted,
    never proposing a specific one.

Read-only: this module never changes an order, inventory, or sends any
customer communication -- see DISCLAIMER.
"""

from services.retail_data_service import RetailDataService
from order_fulfillment_agent.fulfillment_engine import OrderFulfillmentEngine

SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "unable_to_assess": 3, "low": 4, "not_applicable": 5}

PROBLEM_CONFIRMED = "confirmed"
PROBLEM_PREDICTED = "predicted"
PROBLEM_NONE = "none"
PROBLEM_UNKNOWN = "unknown"
PROBLEM_NOT_APPLICABLE = "not_applicable"

DISCLAIMER = (
    "All recommendations are read-only and require human approval. This "
    "agent never changes an order, cancels or refunds anything, transfers "
    "inventory, or sends any customer communication or external API call."
)

NO_ALTERNATIVE_PRODUCT_REASON = (
    "No product substitutability or alternative-product mapping exists in "
    "this dataset (products.csv has no related-product or substitute "
    "field); recommending a specific alternative product would not be "
    "supported by reliable data."
)

NO_POLICY_DATA_REASON = (
    "This project has no compensation/service-recovery policy dataset, so "
    "no specific recovery action (discount, expedite, etc.) can be "
    "recommended from data -- only that a human-reviewed action may be "
    "warranted, left to human judgment."
)


# --------------------------------------------------------------------- #
# Pure functions -- no I/O
# --------------------------------------------------------------------- #
def classify_problem_type(fulfillment_result):
    """Distinguishes a CONFIRMED problem (promised date already passed --
    a fact) from a PREDICTED risk (inventory short but date still future
    -- a forward-looking concern, not yet a fact)."""
    risk_level = fulfillment_result["risk_level"]
    if risk_level == "not_applicable":
        return PROBLEM_NOT_APPLICABLE
    if risk_level == "unable_to_assess":
        return PROBLEM_UNKNOWN
    if fulfillment_result.get("promised_date_passed"):
        return PROBLEM_CONFIRMED
    if fulfillment_result["inventory_readiness"]["sufficient"] is False:
        return PROBLEM_PREDICTED
    return PROBLEM_NONE


def build_explanation(fulfillment_result, problem_type):
    """Plain-language explanation built only from fields already present
    in the fulfillment result -- never a new claim."""
    if problem_type == PROBLEM_NOT_APPLICABLE:
        return f"Order is already {fulfillment_result['order_status']}; no forward-looking customer experience risk applies."
    if problem_type == PROBLEM_CONFIRMED:
        return (
            f"Promised delivery date ({fulfillment_result['promised_delivery_date']}) has "
            f"already passed by {fulfillment_result['days_overdue']} day(s) and the order is "
            f"still {fulfillment_result['order_status']}."
        )
    if problem_type == PROBLEM_PREDICTED:
        shortfall = fulfillment_result["inventory_readiness"]["shortfall"]
        return (
            f"Inventory at the assigned location ({fulfillment_result['fulfillment_location']}) "
            f"is insufficient (shortfall of {shortfall} unit(s)); the promised date has not passed yet, "
            f"so this is a predicted risk, not a confirmed problem."
        )
    if problem_type == PROBLEM_UNKNOWN:
        reasons = []
        if fulfillment_result.get("promised_date_missing"):
            reasons.append("the promised delivery date is missing")
        limitation = fulfillment_result["inventory_readiness"].get("data_limitation")
        if limitation:
            reasons.append(limitation)
        return "Cannot reliably assess this order: " + ("; ".join(reasons) if reasons else "insufficient data.")
    return "No fulfillment risk identified; inventory is sufficient and the promised date (if any) has not passed."


def build_missing_information(fulfillment_result):
    missing = []
    if fulfillment_result.get("promised_date_missing"):
        missing.append("promised_delivery_date is missing for this order")
    limitation = fulfillment_result["inventory_readiness"].get("data_limitation")
    if limitation:
        missing.append(limitation)
    missing.append(
        "No actual_delivery_date, shipment tracking, or carrier data exists in this "
        "dataset -- delivery feasibility beyond inventory readiness and the promised "
        "date is always unknown."
    )
    return missing


def assess_cancellation_risk(fulfillment_result, alternatives_found):
    """Conservative, fully explainable rule -- a flag for human review,
    never a prediction or automatic action. Only trips for the narrowest,
    most evidenced case: already critical, overdue, inventory short at the
    assigned location, AND no alternative location found with sufficient
    stock either."""
    if fulfillment_result["risk_level"] != "critical":
        return False, None
    if not fulfillment_result.get("promised_date_passed"):
        return False, None
    if fulfillment_result["inventory_readiness"]["sufficient"] is not False:
        return False, None
    if alternatives_found:
        return False, None
    return True, (
        "Order is significantly overdue, inventory is insufficient at the assigned "
        "location, and no alternative location with sufficient stock was found. This "
        "pattern is often associated with eventual cancellation -- this is a flag for "
        "human review, not a prediction or automatic action."
    )


def build_recommended_actions(problem_type, inventory_sufficient, severity):
    """Deterministic, read-only recommendation strings."""
    actions = []
    if problem_type in (PROBLEM_CONFIRMED, PROBLEM_PREDICTED, PROBLEM_UNKNOWN):
        actions.append("Verify the latest fulfillment status and estimated delivery date.")
    if inventory_sufficient is False:
        actions.append("Check eligible inventory at alternative locations.")
    if severity in ("critical", "high"):
        actions.append("Route unresolved issue to customer support.")
    if problem_type == PROBLEM_UNKNOWN:
        actions.append("Review this order manually -- insufficient data to assess automatically.")
    return actions


# --------------------------------------------------------------------- #
# Data-orchestration layer
# --------------------------------------------------------------------- #
class CustomerExperienceEngine:
    def __init__(self, service=None, fulfillment_engine=None):
        self.service = service if service is not None else RetailDataService()
        self.fulfillment_engine = (
            fulfillment_engine if fulfillment_engine is not None
            else OrderFulfillmentEngine(service=self.service)
        )

    # ---- shared helpers -------------------------------------------------
    def _marketplace_context(self, sku):
        """New context this agent adds: marketplace listing availability.
        Not computed by any other agent. Explicitly caveated: orders.csv
        does not record which channel an order was placed through, so
        this is general product-availability context, not proof this
        specific order is affected."""
        try:
            listings = self.service.get_marketplace_listings(sku)
        except ValueError:
            return None
        if listings is None or len(listings) == 0:
            return {"has_marketplace_listings": False, "any_availability_issue": False}

        problematic = listings[listings["listing_status"].isin(["OUT_OF_STOCK", "INACTIVE"])]
        if len(problematic) == 0:
            return {"has_marketplace_listings": True, "any_availability_issue": False}
        return {
            "has_marketplace_listings": True,
            "any_availability_issue": True,
            "affected_marketplaces": problematic["marketplace"].tolist(),
            "note": (
                "This SKU has marketplace listing(s) flagged OUT_OF_STOCK/INACTIVE. "
                "This is general product-availability context, not necessarily tied "
                "to this specific order's fulfillment channel -- orders.csv does not "
                "record which channel an order was placed through."
            ),
        }

    # ---- required public functions -------------------------------------
    def analyze_customer_order_experience(self, order_id, reference_date=None):
        """Full single-order customer-experience deep dive. Reuses
        OrderFulfillmentEngine.analyze_order_fulfillment(order_id) for
        every fulfillment/inventory/demand/promotion fact; computes
        nothing about stock or forecasts itself."""
        fulfillment_result = self.fulfillment_engine.analyze_order_fulfillment(order_id, reference_date=reference_date)

        if not fulfillment_result.get("order_found", True):
            return {
                "order_id": order_id, "order_found": False,
                "note": fulfillment_result.get("note", f"No order found with order_id {order_id!r}."),
            }

        problem_type = classify_problem_type(fulfillment_result)
        explanation = build_explanation(fulfillment_result, problem_type)
        missing_information = build_missing_information(fulfillment_result)

        alternatives = fulfillment_result.get("alternative_fulfillment_options") or []
        alternatives_found = any(a.get("sufficient_stock") for a in alternatives)

        cancellation_flagged, cancellation_reason = assess_cancellation_risk(fulfillment_result, alternatives_found)
        marketplace_context = self._marketplace_context(fulfillment_result["sku"])
        recommended_actions = build_recommended_actions(
            problem_type, fulfillment_result["inventory_readiness"]["sufficient"], fulfillment_result["risk_level"]
        )

        return {
            "order_id": fulfillment_result["order_id"],
            "order_found": True,
            "customer_id": fulfillment_result.get("customer_id"),
            "sku": fulfillment_result["sku"],
            "order_status": fulfillment_result["order_status"],
            "fulfillment_location": fulfillment_result["fulfillment_location"],
            "severity": fulfillment_result["risk_level"],
            "problem_type": problem_type,
            "explanation": explanation,
            "missing_information": missing_information,
            "fulfillment_assessment": fulfillment_result,
            "marketplace_context": marketplace_context,
            "potential_cancellation_risk": {"flagged": cancellation_flagged, "reason": cancellation_reason},
            "alternative_product_recommendation": {"available": False, "reason": NO_ALTERNATIVE_PRODUCT_REASON},
            "human_reviewed_recovery_action": {
                "suggested": fulfillment_result["risk_level"] in ("critical", "high"),
                "specific_action": None,
                "reason": NO_POLICY_DATA_REASON,
            },
            "recommended_actions": recommended_actions,
            "disclaimer": DISCLAIMER,
        }

    def get_customer_impact_risks(self, reference_date=None):
        """Every open order with a customer-impacting fulfillment risk
        (critical/high/medium/unable_to_assess), enriched with the CX
        layer. One bad order must not abort the whole scan."""
        at_risk = self.fulfillment_engine.get_orders_at_risk(reference_date=reference_date)
        results = []
        for lean_result in at_risk:
            order_id = lean_result["order_id"]
            try:
                results.append(self.analyze_customer_order_experience(order_id, reference_date=reference_date))
            except Exception as exc:
                results.append({
                    "order_id": order_id, "order_found": True,
                    "severity": "unable_to_assess",
                    "error": f"{type(exc).__name__}: {exc}",
                    "missing_information": [f"Unexpected error analyzing order {order_id!r}: {exc}"],
                    "recommended_actions": ["Review this order manually -- an unexpected error occurred during automated analysis."],
                    "disclaimer": DISCLAIMER,
                })
        results.sort(key=lambda r: SEVERITY_ORDER.get(r.get("severity"), 99))
        return results

    def get_at_risk_customer_orders(self, limit=10, reference_date=None):
        """Top-N prioritized at-risk orders, enriched with the CX layer.
        Reuses OrderFulfillmentEngine's own prioritization/sorting --
        this agent does not re-sort or re-rank by its own criteria."""
        if not isinstance(limit, int) or isinstance(limit, bool) or limit <= 0:
            raise ValueError(f"limit must be a positive integer, got: {limit!r}")

        priorities = self.fulfillment_engine.get_fulfillment_priorities(limit=limit, reference_date=reference_date)
        results = []
        for lean_result in priorities:
            order_id = lean_result["order_id"]
            try:
                results.append(self.analyze_customer_order_experience(order_id, reference_date=reference_date))
            except Exception as exc:
                results.append({
                    "order_id": order_id, "order_found": True,
                    "severity": "unable_to_assess",
                    "error": f"{type(exc).__name__}: {exc}",
                    "missing_information": [f"Unexpected error analyzing order {order_id!r}: {exc}"],
                    "recommended_actions": ["Review this order manually -- an unexpected error occurred during automated analysis."],
                    "disclaimer": DISCLAIMER,
                })
        return results

    def get_service_recovery_recommendations(self, reference_date=None):
        risks = self.get_customer_impact_risks(reference_date=reference_date)
        action_counts = {}
        orders = []
        for r in risks:
            actions = r.get("recommended_actions") or []
            if not actions:
                continue
            orders.append({
                "order_id": r["order_id"], "sku": r.get("sku"), "severity": r.get("severity"),
                "recommended_actions": actions,
            })
            for action in actions:
                action_counts[action] = action_counts.get(action, 0) + 1
        return {
            "total_orders_with_recommendations": len(orders),
            "action_counts": action_counts,
            "orders": orders,
            "disclaimer": DISCLAIMER,
        }

    def get_customer_experience_summary(self, reference_date=None):
        risks = self.get_customer_impact_risks(reference_date=reference_date)
        severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "unable_to_assess": 0}
        problem_type_counts = {PROBLEM_CONFIRMED: 0, PROBLEM_PREDICTED: 0, PROBLEM_UNKNOWN: 0, PROBLEM_NONE: 0}
        cancellation_flagged_count = 0
        marketplace_issue_count = 0

        for r in risks:
            severity = r.get("severity")
            if severity in severity_counts:
                severity_counts[severity] += 1
            problem_type = r.get("problem_type")
            if problem_type in problem_type_counts:
                problem_type_counts[problem_type] += 1
            if (r.get("potential_cancellation_risk") or {}).get("flagged"):
                cancellation_flagged_count += 1
            marketplace_context = r.get("marketplace_context")
            if marketplace_context and marketplace_context.get("any_availability_issue"):
                marketplace_issue_count += 1

        return {
            "total_customer_impact_risks": len(risks),
            "severity_counts": severity_counts,
            "problem_type_counts": problem_type_counts,
            "orders_with_potential_cancellation_risk": cancellation_flagged_count,
            "orders_with_marketplace_availability_issues": marketplace_issue_count,
            "disclaimer": DISCLAIMER,
        }


_default_engine = CustomerExperienceEngine()


def get_customer_impact_risks():
    return _default_engine.get_customer_impact_risks()


def analyze_customer_order_experience(order_id):
    return _default_engine.analyze_customer_order_experience(order_id)


def get_at_risk_customer_orders(limit=10):
    return _default_engine.get_at_risk_customer_orders(limit=limit)


def get_service_recovery_recommendations():
    return _default_engine.get_service_recovery_recommendations()


def get_customer_experience_summary():
    return _default_engine.get_customer_experience_summary()
