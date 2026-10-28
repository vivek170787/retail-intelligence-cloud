"""
RetailIntelligenceOrchestrator: a single business-query entry point over
the five agents that actually exist in this project (confirmed by
inspection, not assumed):
  - Inventory Intelligence       (inventory_agent)
  - Demand Forecasting           (demand_forecasting_agent)
  - Promotion Intelligence       (promotion_agent)
  - Order Fulfillment Intelligence (order_fulfillment_agent)
  - Customer Experience Intelligence (customer_experience_agent)

There is NO separate "Replenishment Recommendation Agent" in this
codebase -- replenishment recommendations are a function
(get_replenishment_recommendations) inside the Inventory Intelligence
Agent. Reconfirmed by inspection before writing this file.

This module WRAPS the existing RetailOrchestrationService (orchestration/
service.py) rather than reconstructing engines -- one RetailDataService
and one instance of each agent's engine is shared, never duplicated.

Routing is deterministic (keyword + SKU-ID/order-ID/store-ID pattern
matching), the same proven pattern already used in every agent's own
llm_explainer.py. No LLM-based query classifier exists anywhere in this
project to reuse, and none is introduced here -- per the task's own
"use deterministic routing rules initially" instruction. handle_query()
therefore works fully without an OpenAI API key; no LLM call happens
anywhere in this module.

Every response is a structured dict (see _build_response) rather than a
free-text string, and every cross-agent workflow invokes only the agents
relevant to that workflow -- never all five for every request. Any
exception raised by a dependent agent is caught per-call and surfaces as
a data gap rather than aborting the whole response.
"""

import re

from orchestration.service import RetailOrchestrationService

CATEGORY_INVENTORY = "inventory_and_stockout_risks"
CATEGORY_DEMAND = "demand_forecast_and_spikes"
CATEGORY_REPLENISHMENT = "replenishment_recommendations"
CATEGORY_PROMOTION = "promotion_readiness_and_stockout_risks"
CATEGORY_FULFILLMENT = "order_fulfillment_risks"
CATEGORY_CUSTOMER_EXPERIENCE = "customer_experience_risks"
CATEGORY_CROSS_AGENT = "cross_agent_retail_analysis"

WORKFLOW_STOCKOUT_PREVENTION = "stockout_prevention"
WORKFLOW_PROMOTION_READINESS = "promotion_readiness"
WORKFLOW_CUSTOMER_EXPERIENCE_PROTECTION = "customer_experience_protection"
WORKFLOW_EXECUTIVE_SUMMARY = "executive_retail_summary"

DISCLAIMER = (
    "All recommendations are read-only and require human approval. This "
    "orchestrator never executes an inventory transfer, purchase order, "
    "order change, refund, promotion activation, or customer communication."
)

_SEVERITY_SCALE = ("critical", "high", "medium", "low", "unable_to_assess", "not_applicable")
_SEVERITY_RANK = {level: i for i, level in enumerate(_SEVERITY_SCALE)}

# Maps every risk/readiness vocabulary actually used by the five agents
# onto the one common severity scale used in this orchestrator's
# responses, rather than inventing a new taxonomy or leaving values
# unmapped.
_SEVERITY_NORMALIZATION = {
    "critical": "critical", "high": "high", "medium": "medium", "low": "low",
    "unable_to_assess": "unable_to_assess", "not_applicable": "not_applicable",
    "insufficient": "high", "sufficient": "low", "cannot_determine": "unable_to_assess",
}

_SKU_PATTERN = re.compile(r"SKU-[A-Z]{3}-\d{4}", re.IGNORECASE)
_ORDER_ID_PATTERN = re.compile(r"ORD-\d{6}", re.IGNORECASE)
_STORE_PATTERN = re.compile(r"ST-\d{3}", re.IGNORECASE)

_REPLENISH_TERMS = ("replenish", "reorder", "restock")
_PROMOTION_TERMS = ("promo", "promotion", "discount")
_DEMAND_TERMS = ("demand", "forecast", "spike", "declin")
_INVENTORY_TERMS = ("inventory", "stock", "stockout", "shortage", "warehouse")
_FULFILLMENT_TERMS = ("fulfillment", "deliver", "shipping", "ship")
_CX_TERMS = ("customer", "experience", "service recovery", "recovery action")
_CROSS_AGENT_TERMS = ("summary", "overview", "executive", "cross-agent", "cross agent", "business", "protect")
_STOCKOUT_PREVENTION_TERMS = ("prevent", "stockout prevention")
_CUSTOMER_PROTECTION_TERMS = ("protect", "at risk customer")


def normalize_severity(value):
    return _SEVERITY_NORMALIZATION.get(value, "unable_to_assess")


def worst_severity(values):
    """Most severe value among a list of native-vocabulary severities,
    on the common scale -- used to roll up one overall severity for a
    multi-item response without hiding any individual bad result."""
    normalized = [normalize_severity(v) for v in values if v is not None]
    if not normalized:
        return "unable_to_assess"
    return min(normalized, key=lambda s: _SEVERITY_RANK.get(s, len(_SEVERITY_SCALE)))


def extract_sku(text):
    match = _SKU_PATTERN.search(text)
    return match.group(0).upper() if match else None


def extract_order_id(text):
    match = _ORDER_ID_PATTERN.search(text)
    return match.group(0).upper() if match else None


def extract_store_id(text):
    match = _STORE_PATTERN.search(text)
    return match.group(0).upper() if match else None


def classify_query(query_text):
    """Deterministic category + (for cross-agent queries) workflow
    classification. No LLM involved -- this project has no existing
    LLM-based classifier to reuse, and the task calls for deterministic
    routing initially."""
    q = query_text.lower()

    # Workflow-specific phrases are checked before generic single-agent
    # category terms, since e.g. "stockout prevention" would otherwise
    # match the plain inventory category first.
    if any(term in q for term in _STOCKOUT_PREVENTION_TERMS):
        return CATEGORY_CROSS_AGENT, WORKFLOW_STOCKOUT_PREVENTION
    if "readiness" in q and any(term in q for term in _PROMOTION_TERMS):
        return CATEGORY_CROSS_AGENT, WORKFLOW_PROMOTION_READINESS
    if any(term in q for term in _CUSTOMER_PROTECTION_TERMS):
        return CATEGORY_CROSS_AGENT, WORKFLOW_CUSTOMER_EXPERIENCE_PROTECTION
    if any(term in q for term in _CROSS_AGENT_TERMS):
        return CATEGORY_CROSS_AGENT, WORKFLOW_EXECUTIVE_SUMMARY

    if any(term in q for term in _CX_TERMS):
        return CATEGORY_CUSTOMER_EXPERIENCE, None
    if any(term in q for term in _REPLENISH_TERMS):
        return CATEGORY_REPLENISHMENT, None
    if any(term in q for term in _PROMOTION_TERMS):
        return CATEGORY_PROMOTION, None
    if any(term in q for term in _FULFILLMENT_TERMS) or (extract_order_id(query_text) and "customer" not in q):
        return CATEGORY_FULFILLMENT, None
    if any(term in q for term in _DEMAND_TERMS):
        return CATEGORY_DEMAND, None
    if any(term in q for term in _INVENTORY_TERMS):
        return CATEGORY_INVENTORY, None

    return CATEGORY_CROSS_AGENT, WORKFLOW_EXECUTIVE_SUMMARY


def _build_response(query_text, category, summary, key_findings, affected_entities,
                     severity, evidence, recommended_actions, data_gaps, agents_used,
                     human_approval_required=True):
    return {
        "query": query_text,
        "category": category,
        "summary": summary,
        "key_findings": key_findings,
        "affected_entities": {
            "skus": affected_entities.get("skus", []),
            "stores": affected_entities.get("stores", []),
            "orders": affected_entities.get("orders", []),
        },
        "severity": severity,
        "evidence": evidence,
        "recommended_actions": recommended_actions,
        "data_gaps_and_uncertainty": data_gaps,
        "agents_used": agents_used,
        "human_approval_required": human_approval_required,
        "disclaimer": DISCLAIMER,
    }


class RetailIntelligenceOrchestrator:
    def __init__(self, orchestration_service=None):
        self.svc = orchestration_service if orchestration_service is not None else RetailOrchestrationService()

    # ---- safe call helper ------------------------------------------------
    @staticmethod
    def _safe_call(agent_name, agents_used, data_gaps, engine, method_name, *args, **kwargs):
        """Calls one agent method by name (resolved here, not by the
        caller), recording it as used; on failure -- including the engine
        not having that method at all, e.g. a missing/stub agent -- records
        a data gap instead of raising. Resolving the method INSIDE this
        try block matters: a pre-resolved bound function reference
        (engine.method) raises AttributeError in the CALLER's frame before
        this helper is even entered if the method doesn't exist, which
        would defeat the whole point of this helper."""
        agents_used.append(agent_name)
        try:
            func = getattr(engine, method_name)
            return func(*args, **kwargs)
        except Exception as exc:
            data_gaps.append(f"{agent_name} agent unavailable or failed: {type(exc).__name__}: {exc}")
            return None

    # ---- single-category handlers ---------------------------------------
    def _handle_inventory(self, query_text, sku, store_id):
        agents_used, data_gaps, key_findings = [], [], []
        affected = {"skus": [], "stores": [], "orders": []}

        if sku:
            result = self._safe_call("inventory", agents_used, data_gaps,
                                      self.svc.inventory_engine, "get_product_inventory_analysis", sku)
            if result is None:
                return _build_response(query_text, CATEGORY_INVENTORY, "Could not retrieve inventory data.",
                                        [], affected, "unable_to_assess", {}, [], data_gaps, agents_used)
            affected["skus"] = [sku]
            severity = normalize_severity(result["estimated"]["risk_level"])
            key_findings.append(
                f"{sku}: {result['observed']['store_available_inventory']} available, "
                f"risk level {result['estimated']['risk_level']}."
            )
            qty = result["recommendation"]["suggested_replenishment_quantity"]
            actions = [f"Investigate replenishment for {sku} (suggested quantity: {qty})."] if qty > 0 else []
            return _build_response(
                query_text, CATEGORY_INVENTORY, f"Inventory status for {sku}.", key_findings, affected,
                severity, {"product_analysis": result}, actions, data_gaps, agents_used,
            )

        summary = self._safe_call("inventory", agents_used, data_gaps, self.svc.inventory_engine, "get_inventory_summary")
        top_risks = None
        if any(t in query_text.lower() for t in ("top", "worst", "biggest")):
            top_risks = self._safe_call("inventory", agents_used, data_gaps, self.svc.inventory_engine, "get_top_stockout_risks")

        if summary is None and top_risks is None:
            return _build_response(query_text, CATEGORY_INVENTORY, "Could not retrieve inventory data.",
                                    [], affected, "unable_to_assess", {}, [], data_gaps, agents_used)

        if summary:
            key_findings.append(
                f"{summary['risk_level_counts'].get('critical', 0)} critical and "
                f"{summary['risk_level_counts'].get('high', 0)} high-risk SKUs out of {summary['total_products']}."
            )
        if top_risks:
            affected["skus"] = [r["sku"] for r in top_risks]
            key_findings.append(f"Top stockout risk SKUs: {', '.join(affected['skus'][:5])}.")

        severity = worst_severity(
            (["critical"] if summary and summary["risk_level_counts"].get("critical") else [])
            + (["high"] if summary and summary["risk_level_counts"].get("high") else [])
            + (["low"] if summary and not top_risks else [])
        )
        return _build_response(
            query_text, CATEGORY_INVENTORY, "Catalog-wide inventory and stockout risk overview.",
            key_findings, affected, severity,
            {"summary": summary, "top_stockout_risks": top_risks}, [], data_gaps, agents_used,
        )

    def _handle_demand(self, query_text, sku, horizon_days):
        agents_used, data_gaps, key_findings = [], [], []
        affected = {"skus": [], "stores": [], "orders": []}
        q = query_text.lower()

        if sku:
            forecast = self._safe_call("demand", agents_used, data_gaps,
                                        self.svc.demand_engine, "forecast_demand", sku, horizon_days=horizon_days)
            if forecast is None:
                return _build_response(query_text, CATEGORY_DEMAND, "Could not retrieve a demand forecast.",
                                        [], affected, "unable_to_assess", {}, [], data_gaps, agents_used)
            affected["skus"] = [sku]
            severity = "low" if forecast["sufficient_data"] else "unable_to_assess"
            key_findings.append(
                f"{sku}: forecast total demand {forecast['total_forecast_demand']} over {horizon_days} day(s)."
                if forecast["sufficient_data"] else f"{sku}: insufficient history to forecast demand."
            )
            return _build_response(query_text, CATEGORY_DEMAND, f"Demand forecast for {sku}.", key_findings,
                                    affected, severity, {"forecast": forecast}, [], data_gaps, agents_used)

        if "declin" in q:
            declines = self._safe_call("demand", agents_used, data_gaps, self.svc.demand_engine, "detect_declining_demand")
            affected["skus"] = [d["sku"] for d in (declines or [])]
            key_findings.append(f"{len(declines or [])} SKU(s) show declining demand.")
            return _build_response(query_text, CATEGORY_DEMAND, "Declining demand scan.", key_findings, affected,
                                    "medium" if declines else "low", {"declining_demand": declines}, [], data_gaps, agents_used)

        spikes = self._safe_call("demand", agents_used, data_gaps, self.svc.demand_engine, "detect_demand_spikes")
        if spikes is not None:
            affected["skus"] = [s["sku"] for s in spikes]
            key_findings.append(f"{len(spikes)} SKU(s) show a demand spike.")
        summary = self._safe_call("demand", agents_used, data_gaps, self.svc.demand_engine, "get_demand_summary")
        return _build_response(
            query_text, CATEGORY_DEMAND, "Demand forecast and spike overview.", key_findings, affected,
            "medium" if spikes else "low", {"demand_spikes": spikes, "summary": summary}, [], data_gaps, agents_used,
        )

    def _handle_replenishment(self, query_text, sku):
        agents_used, data_gaps, key_findings = [], [], []
        affected = {"skus": [], "stores": [], "orders": []}

        if sku:
            result = self._safe_call("inventory", agents_used, data_gaps,
                                      self.svc.inventory_engine, "get_product_inventory_analysis", sku)
            if result is None:
                return _build_response(query_text, CATEGORY_REPLENISHMENT, "Could not retrieve replenishment data.",
                                        [], affected, "unable_to_assess", {}, [], data_gaps, agents_used)
            affected["skus"] = [sku]
            qty = result["recommendation"]["suggested_replenishment_quantity"]
            key_findings.append(f"{sku}: suggested replenishment quantity {qty}.")
            actions = ["Investigate replenishment before stock runs out."] if qty > 0 else []
            return _build_response(query_text, CATEGORY_REPLENISHMENT, f"Replenishment recommendation for {sku}.",
                                    key_findings, affected, "low" if qty == 0 else "medium",
                                    {"product_analysis": result}, actions, data_gaps, agents_used)

        recs = self._safe_call("inventory", agents_used, data_gaps, self.svc.inventory_engine, "get_replenishment_recommendations")
        if recs is None:
            return _build_response(query_text, CATEGORY_REPLENISHMENT, "Could not retrieve replenishment data.",
                                    [], affected, "unable_to_assess", {}, [], data_gaps, agents_used)
        affected["skus"] = [r["sku"] for r in recs]
        key_findings.append(f"{len(recs)} SKU(s) have a positive suggested replenishment quantity.")
        return _build_response(
            query_text, CATEGORY_REPLENISHMENT, "Catalog-wide replenishment recommendations.", key_findings, affected,
            "medium" if recs else "low", {"replenishment_recommendations": recs},
            ["Investigate replenishment for the listed SKUs before stock runs out."] if recs else [],
            data_gaps, agents_used,
        )

    def _handle_promotion(self, query_text, sku):
        agents_used, data_gaps, key_findings = [], [], []
        affected = {"skus": [], "stores": [], "orders": []}
        q = query_text.lower()

        if sku:
            result = self._safe_call("promotion", agents_used, data_gaps,
                                      self.svc.promotion_engine, "analyze_promotion_for_sku", sku)
            if result is None:
                return _build_response(query_text, CATEGORY_PROMOTION, "Could not retrieve promotion data.",
                                        [], affected, "unable_to_assess", {}, [], data_gaps, agents_used)
            affected["skus"] = [sku]
            if not result["has_promotion_history"]:
                return _build_response(query_text, CATEGORY_PROMOTION, f"No promotion history found for {sku}.",
                                        [], affected, "low", {"sku_analysis": result}, [], data_gaps, agents_used)
            severities = [r["readiness_status"] for r in result["readiness_reports"]]
            key_findings.append(f"{sku}: {len(result['promotions'])} promotion(s) on record.")
            return _build_response(query_text, CATEGORY_PROMOTION, f"Promotion analysis for {sku}.", key_findings,
                                    affected, worst_severity(severities), {"sku_analysis": result}, [], data_gaps, agents_used)

        if "stockout" in q or "risk" in q:
            risks = self._safe_call("promotion", agents_used, data_gaps, self.svc.promotion_engine, "get_promotion_stockout_risks")
            affected["skus"] = [r["sku"] for r in (risks or [])]
            key_findings.append(f"{len(risks or [])} promotion(s) with a confirmed stockout risk.")
            return _build_response(query_text, CATEGORY_PROMOTION, "Promotion stockout risk scan.", key_findings,
                                    affected, "high" if risks else "low", {"stockout_risks": risks}, [], data_gaps, agents_used)

        report = self._safe_call("promotion", agents_used, data_gaps, self.svc.promotion_engine, "get_promotion_readiness_report")
        if report is None:
            return _build_response(query_text, CATEGORY_PROMOTION, "Could not retrieve promotion readiness data.",
                                    [], affected, "unable_to_assess", {}, [], data_gaps, agents_used)
        affected["skus"] = [r["sku"] for r in report["reports"]]
        key_findings.append(f"{report['total_promotions_assessed']} upcoming/active promotion(s) assessed.")
        severity = worst_severity([r["readiness_status"] for r in report["reports"]])
        return _build_response(query_text, CATEGORY_PROMOTION, "Promotion readiness overview.", key_findings,
                                affected, severity, {"readiness_report": report}, [], data_gaps, agents_used)

    def _handle_fulfillment(self, query_text, order_id, limit):
        agents_used, data_gaps, key_findings = [], [], []
        affected = {"skus": [], "stores": [], "orders": []}
        q = query_text.lower()

        if order_id:
            result = self._safe_call("fulfillment", agents_used, data_gaps,
                                      self.svc.fulfillment_engine, "analyze_order_fulfillment", order_id)
            if result is None or not result.get("order_found", True):
                return _build_response(query_text, CATEGORY_FULFILLMENT,
                                        result.get("note", "Order not found.") if result else "Could not retrieve order data.",
                                        [], affected, "unable_to_assess", {}, [], data_gaps, agents_used)
            affected["orders"] = [order_id]
            affected["skus"] = [result["sku"]]
            key_findings.append(f"{order_id}: risk level {result['risk_level']}.")
            return _build_response(query_text, CATEGORY_FULFILLMENT, f"Fulfillment analysis for {order_id}.",
                                    key_findings, affected, normalize_severity(result["risk_level"]),
                                    {"order_analysis": result}, result.get("recommendations", []), data_gaps, agents_used)

        if "today" in q:
            due = self._safe_call("fulfillment", agents_used, data_gaps, self.svc.fulfillment_engine, "get_orders_due_today")
            affected["orders"] = [o["order_id"] for o in (due or [])]
            key_findings.append(f"{len(due or [])} order(s) due today or overdue.")
            return _build_response(query_text, CATEGORY_FULFILLMENT, "Orders due today or overdue.", key_findings,
                                    affected, "high" if due else "low", {"orders_due_today": due}, [], data_gaps, agents_used)

        if "shortage" in q or "inventory" in q:
            shortages = self._safe_call("fulfillment", agents_used, data_gaps, self.svc.fulfillment_engine, "get_orders_with_inventory_shortages")
            affected["orders"] = [o["order_id"] for o in (shortages or [])]
            key_findings.append(f"{len(shortages or [])} order(s) blocked by an inventory shortage.")
            return _build_response(query_text, CATEGORY_FULFILLMENT, "Orders with inventory shortages.", key_findings,
                                    affected, "high" if shortages else "low", {"shortages": shortages}, [], data_gaps, agents_used)

        priorities = self._safe_call("fulfillment", agents_used, data_gaps, self.svc.fulfillment_engine, "get_fulfillment_priorities", limit=limit)
        summary = self._safe_call("fulfillment", agents_used, data_gaps, self.svc.fulfillment_engine, "get_fulfillment_risk_summary")
        affected["orders"] = [o["order_id"] for o in (priorities or [])]
        key_findings.append(f"Top {len(priorities or [])} priority at-risk order(s).")
        severity = worst_severity([o["risk_level"] for o in (priorities or [])])
        return _build_response(query_text, CATEGORY_FULFILLMENT, "Order fulfillment risk overview.", key_findings,
                                affected, severity, {"priorities": priorities, "summary": summary}, [], data_gaps, agents_used)

    def _handle_customer_experience(self, query_text, order_id, limit):
        agents_used, data_gaps, key_findings = [], [], []
        affected = {"skus": [], "stores": [], "orders": []}
        q = query_text.lower()

        if order_id:
            result = self._safe_call("customer_experience", agents_used, data_gaps,
                                      self.svc.cx_engine, "analyze_customer_order_experience", order_id)
            if result is None or not result.get("order_found", True):
                return _build_response(query_text, CATEGORY_CUSTOMER_EXPERIENCE,
                                        result.get("note", "Order not found.") if result else "Could not retrieve order data.",
                                        [], affected, "unable_to_assess", {}, [], data_gaps, agents_used)
            affected["orders"] = [order_id]
            affected["skus"] = [result["sku"]]
            key_findings.append(f"{order_id}: severity {result['severity']}, problem type {result['problem_type']}.")
            return _build_response(query_text, CATEGORY_CUSTOMER_EXPERIENCE, f"Customer experience analysis for {order_id}.",
                                    key_findings, affected, normalize_severity(result["severity"]),
                                    {"order_experience": result}, result.get("recommended_actions", []), data_gaps, agents_used)

        if any(t in q for t in ("recovery", "recommend")):
            recovery = self._safe_call("customer_experience", agents_used, data_gaps, self.svc.cx_engine, "get_service_recovery_recommendations")
            affected["orders"] = [o["order_id"] for o in (recovery or {}).get("orders", [])]
            key_findings.append(f"{(recovery or {}).get('total_orders_with_recommendations', 0)} order(s) have a recommended action.")
            return _build_response(query_text, CATEGORY_CUSTOMER_EXPERIENCE, "Service recovery recommendations.",
                                    key_findings, affected, "medium" if recovery and recovery["orders"] else "low",
                                    {"service_recovery": recovery}, [], data_gaps, agents_used)

        at_risk = self._safe_call("customer_experience", agents_used, data_gaps, self.svc.cx_engine, "get_at_risk_customer_orders", limit=limit)
        summary = self._safe_call("customer_experience", agents_used, data_gaps, self.svc.cx_engine, "get_customer_experience_summary")
        affected["orders"] = [o["order_id"] for o in (at_risk or [])]
        key_findings.append(f"Top {len(at_risk or [])} priority at-risk customer order(s).")
        severity = worst_severity([o["severity"] for o in (at_risk or [])])
        return _build_response(query_text, CATEGORY_CUSTOMER_EXPERIENCE, "Customer experience risk overview.",
                                key_findings, affected, severity, {"at_risk_orders": at_risk, "summary": summary}, [], data_gaps, agents_used)

    # ---- cross-agent workflows (Examples A-D) ----------------------------
    def stockout_prevention_workflow(self, sku=None, horizon_days=7, limit=10):
        """A: Inventory risks -> demand forecast -> replenishment
        recommendations -> available warehouse stock."""
        agents_used, data_gaps, key_findings = [], [], []
        affected = {"skus": [], "stores": [], "orders": []}
        evidence = {}

        if sku:
            inv = self._safe_call("inventory", agents_used, data_gaps, self.svc.inventory_engine, "get_product_inventory_analysis", sku)
            forecast = self._safe_call("demand", agents_used, data_gaps, self.svc.demand_engine, "forecast_demand", sku, horizon_days=horizon_days)
            affected["skus"] = [sku]
            evidence = {"inventory": inv, "forecast": forecast}
            if inv:
                key_findings.append(f"{sku}: {inv['observed']['store_available_inventory']} available, risk {inv['estimated']['risk_level']}.")
            if forecast and forecast["sufficient_data"]:
                key_findings.append(f"{sku}: forecast demand {forecast['total_forecast_demand']} over {horizon_days} day(s).")
            severity = normalize_severity(inv["estimated"]["risk_level"]) if inv else "unable_to_assess"
            actions = (inv["estimated"].get("recommendations") if inv else None) or []
            return _build_response(f"Stockout prevention analysis for {sku}", CATEGORY_CROSS_AGENT, "Single-SKU stockout prevention review.",
                                    key_findings, affected, severity, evidence, actions, data_gaps, agents_used)

        top_risks = self._safe_call("inventory", agents_used, data_gaps, self.svc.inventory_engine, "get_top_stockout_risks", limit=limit)
        replenishment = self._safe_call("inventory", agents_used, data_gaps, self.svc.inventory_engine, "get_replenishment_recommendations")

        # Only forecast demand for the flagged top-risk SKUs, not the whole catalog.
        forecasts = {}
        if top_risks:
            for r in top_risks:
                f = self._safe_call("demand", agents_used, data_gaps, self.svc.demand_engine, "forecast_demand", r["sku"], horizon_days=horizon_days)
                if f is not None:
                    forecasts[r["sku"]] = f

        affected["skus"] = [r["sku"] for r in (top_risks or [])]
        key_findings.append(f"{len(top_risks or [])} SKU(s) flagged as top stockout risks.")
        key_findings.append(f"{len(replenishment or [])} SKU(s) have a positive suggested replenishment quantity.")
        severity = worst_severity([r["estimated"]["risk_level"] for r in (top_risks or [])])
        return _build_response(
            "Stockout prevention: inventory risk -> demand forecast -> replenishment -> warehouse stock",
            CATEGORY_CROSS_AGENT, "Catalog-wide stockout prevention workflow.", key_findings, affected, severity,
            {"top_stockout_risks": top_risks, "demand_forecasts": forecasts, "replenishment_recommendations": replenishment},
            ["Investigate replenishment for the listed top-risk SKUs."] if top_risks else [], data_gaps, agents_used,
        )

    def promotion_readiness_workflow(self, days_ahead=14):
        """B: Upcoming promotions -> expected demand -> inventory
        availability -> replenishment feasibility -> promotion risk report.
        Reuses PromotionIntelligenceEngine.get_promotion_readiness_report()
        (which already composes demand + inventory internally) and adds
        inventory_agent's own replenishment suggestion as a "feasibility"
        cross-check for each insufficient promotion -- a genuinely new
        cross-reference, not a recomputation of what the promotion report
        already does."""
        agents_used, data_gaps, key_findings = [], [], []
        affected = {"skus": [], "stores": [], "orders": []}

        report = self._safe_call("promotion", agents_used, data_gaps,
                                  self.svc.promotion_engine, "get_promotion_readiness_report", days_ahead=days_ahead)
        if report is None:
            return _build_response("Promotion readiness workflow", CATEGORY_CROSS_AGENT, "Could not retrieve promotion readiness data.",
                                    [], affected, "unable_to_assess", {}, [], data_gaps, agents_used)

        insufficient = [r for r in report["reports"] if r["readiness_status"] == "insufficient"]
        replenishment_feasibility = {}
        for r in insufficient:
            inv = self._safe_call("inventory", agents_used, data_gaps, self.svc.inventory_engine, "get_product_inventory_analysis", r["sku"])
            if inv is not None:
                replenishment_feasibility[r["sku"]] = {
                    "inventory_agent_suggested_replenishment_quantity": inv["recommendation"]["suggested_replenishment_quantity"],
                    "capped_by_warehouse_availability": inv["recommendation"]["capped_by_warehouse_availability"],
                }

        affected["skus"] = [r["sku"] for r in report["reports"]]
        key_findings.append(f"{report['total_promotions_assessed']} upcoming/active promotion(s) assessed.")
        key_findings.append(f"{len(insufficient)} promotion(s) have insufficient inventory readiness.")
        severity = worst_severity([r["readiness_status"] for r in report["reports"]])
        return _build_response(
            "Promotion readiness: upcoming promotions -> expected demand -> inventory -> replenishment feasibility",
            CATEGORY_CROSS_AGENT, "Promotion readiness workflow with replenishment feasibility cross-check.",
            key_findings, affected, severity,
            {"readiness_report": report, "replenishment_feasibility": replenishment_feasibility},
            ["Investigate replenishment before the promotion starts for the listed insufficient SKUs."] if insufficient else [],
            data_gaps, agents_used,
        )

    def customer_experience_protection_workflow(self, limit=10):
        """C: Fulfillment risks -> inventory shortages -> alternative
        fulfillment options -> customer impact -> recovery actions.
        Reuses CustomerExperienceEngine.get_at_risk_customer_orders() and
        get_service_recovery_recommendations() directly, since the
        Customer Experience Agent already implements this exact chain
        internally via OrderFulfillmentEngine."""
        agents_used, data_gaps, key_findings = [], [], []
        affected = {"skus": [], "stores": [], "orders": []}

        at_risk = self._safe_call("customer_experience", agents_used, data_gaps, self.svc.cx_engine, "get_at_risk_customer_orders", limit=limit)
        recovery = self._safe_call("customer_experience", agents_used, data_gaps, self.svc.cx_engine, "get_service_recovery_recommendations")

        affected["orders"] = [o["order_id"] for o in (at_risk or [])]
        affected["skus"] = [o["sku"] for o in (at_risk or []) if o.get("sku")]
        key_findings.append(f"{len(at_risk or [])} priority at-risk customer order(s).")
        key_findings.append(f"{(recovery or {}).get('total_orders_with_recommendations', 0)} order(s) have a recommended recovery action.")
        severity = worst_severity([o["severity"] for o in (at_risk or [])])
        return _build_response(
            "Customer experience protection: fulfillment risk -> inventory -> alternatives -> customer impact -> recovery",
            CATEGORY_CROSS_AGENT, "Customer experience protection workflow.", key_findings, affected, severity,
            {"at_risk_customer_orders": at_risk, "service_recovery_recommendations": recovery}, [], data_gaps, agents_used,
        )

    def executive_retail_summary_workflow(self):
        """D: Combine available inventory, demand, promotion, fulfillment,
        and customer experience insights into one concise summary. The
        one workflow with no existing single-agent equivalent -- genuinely
        new synthesis, built only from each agent's own lightweight
        summary function (cheap: five summary calls, no heavy per-item loops)."""
        agents_used, data_gaps, key_findings = [], [], []
        affected = {"skus": [], "stores": [], "orders": []}

        inventory_summary = self._safe_call("inventory", agents_used, data_gaps, self.svc.inventory_engine, "get_inventory_summary")
        demand_summary = self._safe_call("demand", agents_used, data_gaps, self.svc.demand_engine, "get_demand_summary")
        promotion_summary = self._safe_call("promotion", agents_used, data_gaps, self.svc.promotion_engine, "get_promotional_demand_summary")
        fulfillment_summary = self._safe_call("fulfillment", agents_used, data_gaps, self.svc.fulfillment_engine, "get_fulfillment_risk_summary")
        cx_summary = self._safe_call("customer_experience", agents_used, data_gaps, self.svc.cx_engine, "get_customer_experience_summary")

        if inventory_summary:
            key_findings.append(
                f"Inventory: {inventory_summary['risk_level_counts'].get('critical', 0)} critical, "
                f"{inventory_summary['risk_level_counts'].get('high', 0)} high-risk SKU(s)."
            )
        if demand_summary:
            key_findings.append(
                f"Demand: {demand_summary.get('products_with_demand_spike', 0)} spike(s), "
                f"{demand_summary.get('products_with_declining_demand', 0)} decline(s) detected."
            )
        if promotion_summary:
            total_assessed = promotion_summary.get("upcoming_or_active_promotions_in_window", 0)
            insufficient = promotion_summary["readiness_counts"].get("insufficient", 0)
            cannot_determine = promotion_summary["readiness_counts"].get("cannot_determine", 0)
            key_findings.append(
                f"Promotions: {total_assessed} upcoming/active, {insufficient} insufficient, "
                f"{cannot_determine} could not be assessed."
            )
            # The promotion agent's own bulk resilience silently converts
            # per-item failures (e.g. the inventory agent being down) into
            # "cannot_determine" rather than raising -- so a clean call here
            # can still hide a real outage. Surface it explicitly rather
            # than letting "0 insufficient" read as "everything is fine".
            if total_assessed > 0 and cannot_determine == total_assessed:
                data_gaps.append(
                    "Promotion readiness could not be determined for any upcoming/active "
                    "promotion (the dependent Inventory or Demand agent may be unavailable); "
                    "the insufficient count above does not reflect a confirmed state."
                )
        if fulfillment_summary:
            key_findings.append(
                f"Fulfillment: {fulfillment_summary['risk_counts'].get('critical', 0)} critical open order(s)."
            )
        if cx_summary:
            key_findings.append(
                f"Customer experience: {cx_summary.get('total_customer_impact_risks', 0)} order(s) with customer impact."
            )

        promotion_fully_undetermined = bool(
            promotion_summary
            and promotion_summary.get("upcoming_or_active_promotions_in_window", 0) > 0
            and promotion_summary["readiness_counts"].get("cannot_determine", 0)
            == promotion_summary["upcoming_or_active_promotions_in_window"]
        )
        base_severity = worst_severity([
            "critical" if inventory_summary and inventory_summary["risk_level_counts"].get("critical") else "low",
            "critical" if fulfillment_summary and fulfillment_summary["risk_counts"].get("critical") else "low",
            "high" if promotion_summary and promotion_summary["readiness_counts"].get("insufficient") else "low",
        ])
        # worst_severity's scale ranks a confirmed "low" as more notable
        # than "unable_to_assess" (by design, elsewhere, for surfacing a
        # real-but-mild finding over an absence of data) -- which would
        # wrongly bury this signal if mixed into that same list. Only
        # escalate to unable_to_assess here when nothing else already
        # confirmed a worse finding.
        severity = "unable_to_assess" if (promotion_fully_undetermined and base_severity == "low") else base_severity
        return _build_response(
            "Executive retail summary", CATEGORY_CROSS_AGENT,
            "Combined executive summary across inventory, demand, promotion, fulfillment, and customer experience.",
            key_findings, affected, severity,
            {
                "inventory": inventory_summary, "demand": demand_summary, "promotion": promotion_summary,
                "fulfillment": fulfillment_summary, "customer_experience": cx_summary,
            },
            [], data_gaps, agents_used,
        )

    # ---- main entry point -------------------------------------------------
    def handle_query(self, query_text, sku=None, order_id=None, store_id=None, horizon_days=7, limit=10):
        if not isinstance(query_text, str) or not query_text.strip():
            raise ValueError(f"query_text must be a non-empty string, got: {query_text!r}")

        category, workflow = classify_query(query_text)
        sku = sku or extract_sku(query_text)
        order_id = order_id or extract_order_id(query_text)
        store_id = store_id or extract_store_id(query_text)

        if category == CATEGORY_INVENTORY:
            return self._handle_inventory(query_text, sku, store_id)
        if category == CATEGORY_DEMAND:
            return self._handle_demand(query_text, sku, horizon_days)
        if category == CATEGORY_REPLENISHMENT:
            return self._handle_replenishment(query_text, sku)
        if category == CATEGORY_PROMOTION:
            return self._handle_promotion(query_text, sku)
        if category == CATEGORY_FULFILLMENT:
            return self._handle_fulfillment(query_text, order_id, limit)
        if category == CATEGORY_CUSTOMER_EXPERIENCE:
            return self._handle_customer_experience(query_text, order_id, limit)

        # CATEGORY_CROSS_AGENT
        if workflow == WORKFLOW_STOCKOUT_PREVENTION:
            return self.stockout_prevention_workflow(sku=sku, horizon_days=horizon_days, limit=limit)
        if workflow == WORKFLOW_PROMOTION_READINESS:
            return self.promotion_readiness_workflow()
        if workflow == WORKFLOW_CUSTOMER_EXPERIENCE_PROTECTION:
            return self.customer_experience_protection_workflow(limit=limit)
        return self.executive_retail_summary_workflow()


_default_orchestrator = RetailIntelligenceOrchestrator()


def handle_query(query_text, sku=None, order_id=None, store_id=None, horizon_days=7, limit=10):
    return _default_orchestrator.handle_query(
        query_text, sku=sku, order_id=order_id, store_id=store_id, horizon_days=horizon_days, limit=limit
    )
