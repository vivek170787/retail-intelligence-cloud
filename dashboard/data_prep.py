"""
Dashboard data preparation layer.

Deliberately has NO Streamlit import and performs NO business-logic
calculations of its own -- it only calls the existing agents (via a
RetailIntelligenceOrchestrator / RetailOrchestrationService) and reshapes
their already-computed results into flat records/DataFrames convenient for
rendering. This separation is what makes this module plainly unit
testable (see tests/test_dashboard_data_prep.py) without needing Streamlit
or a browser, and keeps the UI layer (dashboard/app.py, dashboard/pages/*)
free of any reimplemented risk/forecast/readiness logic.

The one piece of genuinely new logic here is building a historical daily
sales series for charting -- and even that reuses demand_forecasting_agent's
own pure, already-tested functions (dedupe_transactions, clean_quantities,
global_confirmed_dates, build_daily_series) rather than re-deriving the
confirmed-coverage methodology from scratch.
"""

import pandas as pd

from demand_forecasting_agent.forecasting_engine import (
    build_daily_series,
    clean_quantities,
    dedupe_transactions,
    global_confirmed_dates,
)

DATASET_WINDOW_NOTE = (
    "Synthetic dataset: 90 days of POS history ending 2026-10-26. "
    "Figures reflect this fixed dataset, not a live feed."
)


def _safe(fn, *args, **kwargs):
    """Calls a data-fetching function, returning (result, error_message).
    Used so one failing/unavailable agent never crashes a whole page --
    the caller decides how to render the error_message, never fabricating
    a value in its place."""
    try:
        return fn(*args, **kwargs), None
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"


# --------------------------------------------------------------------- #
# Command Center
# --------------------------------------------------------------------- #
def build_command_center(orchestrator, days_ahead=7):
    """Top-level KPIs and highlights. Reuses executive_retail_summary_workflow
    (already combines all five agents) plus two lightweight, targeted calls
    for lists the executive summary doesn't itself enumerate."""
    summary, summary_error = _safe(orchestrator.executive_retail_summary_workflow)
    svc = orchestrator.svc

    upcoming_promotions, promo_error = _safe(svc.promotion_engine.get_upcoming_promotions, days_ahead=days_ahead)
    recovery, recovery_error = _safe(svc.cx_engine.get_service_recovery_recommendations)

    evidence = (summary or {}).get("evidence", {})
    errors = [e for e in (summary_error, promo_error, recovery_error) if e]

    return {
        "dataset_note": DATASET_WINDOW_NOTE,
        "severity": (summary or {}).get("severity", "unable_to_assess"),
        "key_findings": (summary or {}).get("key_findings", []),
        "data_gaps": list((summary or {}).get("data_gaps_and_uncertainty", [])) + errors,
        "inventory_summary": evidence.get("inventory"),
        "demand_summary": evidence.get("demand"),
        "promotion_summary": evidence.get("promotion"),
        "fulfillment_summary": evidence.get("fulfillment"),
        "cx_summary": evidence.get("customer_experience"),
        "upcoming_promotions_count": len(upcoming_promotions) if upcoming_promotions is not None else None,
        "recommended_actions": recovery,
    }


# --------------------------------------------------------------------- #
# Inventory & Demand
# --------------------------------------------------------------------- #
def flatten_inventory_risk(r):
    product = r.get("product") or {}
    return {
        "sku": r["sku"],
        "product_name": product.get("product_name"),
        "category": product.get("category"),
        "store_available": r["observed"]["store_available_inventory"],
        "avg_daily_sales_7d": r["estimated"]["avg_daily_sales_7d"],
        "days_of_inventory": r["estimated"]["days_of_inventory"],
        "risk_level": r["estimated"]["risk_level"],
        "is_excess_inventory": r["estimated"]["is_excess_inventory"],
        "suggested_replenishment_qty": r["recommendation"]["suggested_replenishment_quantity"],
    }


def build_inventory_table(orchestrator):
    risks, error = _safe(orchestrator.svc.inventory_engine.get_inventory_risks)
    if risks is None:
        return pd.DataFrame(), error
    return pd.DataFrame([flatten_inventory_risk(r) for r in risks]), None


def build_replenishment_table(orchestrator):
    recs, error = _safe(orchestrator.svc.inventory_engine.get_replenishment_recommendations)
    if recs is None:
        return pd.DataFrame(), error
    return pd.DataFrame([flatten_inventory_risk(r) for r in recs]), None


def build_store_breakdown(orchestrator, sku):
    analysis, error = _safe(orchestrator.svc.inventory_engine.get_product_inventory_analysis, sku)
    if analysis is None:
        return pd.DataFrame(), None, error
    return pd.DataFrame(analysis["observed"]["store_breakdown"]), analysis, None


def build_sales_history_series(orchestrator, sku):
    """Confirmed-coverage daily sales series for one SKU, using the exact
    same methodology as the Demand Forecasting Agent itself."""
    service = orchestrator.svc.service
    try:
        sku_sales = service.get_sales_by_sku(sku)
        all_sales = service.get_sales()
    except Exception as exc:
        return pd.Series(dtype=float), f"{type(exc).__name__}: {exc}"

    sku_sales = dedupe_transactions(sku_sales)
    sku_sales, _ = clean_quantities(sku_sales)
    all_sales = dedupe_transactions(all_sales)
    all_sales, _ = clean_quantities(all_sales)
    confirmed_dates = global_confirmed_dates(all_sales)
    series, _ = build_daily_series(sku_sales, confirmed_dates)
    return series, None


def build_catalog_sales_history_series(orchestrator):
    """Catalog-wide confirmed-coverage daily sales series -- the exact same
    methodology as build_sales_history_series above, applied to every
    product's transactions combined instead of one SKU's. No new
    aggregation rule is introduced: confirmed_dates and the series itself
    are both derived from the same unfiltered `all_sales` frame, so this
    is the identical pure-function pipeline, just not pre-filtered to a
    single SKU."""
    service = orchestrator.svc.service
    try:
        all_sales = service.get_sales()
    except Exception as exc:
        return pd.Series(dtype=float), f"{type(exc).__name__}: {exc}"

    all_sales = dedupe_transactions(all_sales)
    all_sales, _ = clean_quantities(all_sales)
    confirmed_dates = global_confirmed_dates(all_sales)
    series, _ = build_daily_series(all_sales, confirmed_dates)
    return series, None


def build_demand_forecast(orchestrator, sku, horizon_days=7):
    return _safe(orchestrator.svc.demand_engine.forecast_demand, sku, horizon_days=horizon_days)


def build_top_forecasted_products(orchestrator, horizon_days=7, limit=10):
    results, error = _safe(orchestrator.svc.demand_engine.get_top_forecasted_products, horizon_days=horizon_days, limit=limit)
    if results is None:
        return pd.DataFrame(), error
    rows = [{"sku": r["sku"], "product_name": r["product_name"], "total_forecast_demand": r["total_forecast_demand"]} for r in results]
    return pd.DataFrame(rows), None


# --------------------------------------------------------------------- #
# Promotion Intelligence
# --------------------------------------------------------------------- #
def build_upcoming_promotions_table(orchestrator, days_ahead=14):
    promos, error = _safe(orchestrator.svc.promotion_engine.get_upcoming_promotions, days_ahead=days_ahead)
    if promos is None:
        return pd.DataFrame(), error
    return pd.DataFrame(promos), None


def build_promotion_readiness(orchestrator, days_ahead=14):
    return _safe(orchestrator.svc.promotion_engine.get_promotion_readiness_report, days_ahead=days_ahead)


def flatten_readiness_report(r):
    return {
        "promotion_id": r["promotion_id"],
        "sku": r["sku"],
        "status": r["status"],
        "days_until_start": r["days_until_start"],
        "baseline_forecast_demand": r["baseline_forecast_demand"],
        "promotional_demand_source": r["promotional_demand_estimate"]["source"],
        "estimated_promotional_demand": r["promotional_demand_estimate"]["estimated_total_demand"],
        "current_available_inventory": r["observed"]["current_available_inventory"],
        "demand_gap": r["demand_gap"],
        "readiness_status": r["readiness_status"],
    }


def build_demand_spikes_table(orchestrator):
    spikes, error = _safe(orchestrator.svc.demand_engine.detect_demand_spikes)
    if spikes is None:
        return pd.DataFrame(), error
    return pd.DataFrame(spikes), None


# --------------------------------------------------------------------- #
# Order Fulfillment
# --------------------------------------------------------------------- #
def flatten_fulfillment_order(o):
    return {
        "order_id": o["order_id"],
        "sku": o["sku"],
        "order_status": o["order_status"],
        "fulfillment_location": o["fulfillment_location"],
        "promised_delivery_date": o.get("promised_delivery_date"),
        "days_overdue": o.get("days_overdue"),
        "days_until_due": o.get("days_until_due"),
        "risk_level": o["risk_level"],
        "inventory_sufficient": o["inventory_readiness"]["sufficient"],
    }


def build_orders_at_risk_table(orchestrator):
    orders, error = _safe(orchestrator.svc.fulfillment_engine.get_orders_at_risk)
    if orders is None:
        return pd.DataFrame(), error
    return pd.DataFrame([flatten_fulfillment_order(o) for o in orders]), None


def build_orders_due_today_table(orchestrator):
    orders, error = _safe(orchestrator.svc.fulfillment_engine.get_orders_due_today)
    if orders is None:
        return pd.DataFrame(), error
    return pd.DataFrame([flatten_fulfillment_order(o) for o in orders]), None


def build_inventory_blocked_orders_table(orchestrator):
    orders, error = _safe(orchestrator.svc.fulfillment_engine.get_orders_with_inventory_shortages)
    if orders is None:
        return pd.DataFrame(), error
    return pd.DataFrame([flatten_fulfillment_order(o) for o in orders]), None


def build_fulfillment_priorities_table(orchestrator, limit=10):
    orders, error = _safe(orchestrator.svc.fulfillment_engine.get_fulfillment_priorities, limit=limit)
    if orders is None:
        return pd.DataFrame(), error
    return pd.DataFrame([flatten_fulfillment_order(o) for o in orders]), None


def build_order_fulfillment_detail(orchestrator, order_id):
    return _safe(orchestrator.svc.fulfillment_engine.analyze_order_fulfillment, order_id)


def build_alternative_fulfillment_options(orchestrator, order_id):
    result, error = _safe(orchestrator.svc.fulfillment_engine.find_alternative_fulfillment_options, order_id)
    if result is None:
        return pd.DataFrame(), None, error
    return pd.DataFrame(result.get("alternative_candidates", [])), result, None


# --------------------------------------------------------------------- #
# Customer Experience
# --------------------------------------------------------------------- #
def flatten_cx_order(o):
    cancellation = o.get("potential_cancellation_risk") or {}
    return {
        "order_id": o.get("order_id"),
        "sku": o.get("sku"),
        "customer_id": o.get("customer_id"),
        "severity": o.get("severity"),
        "problem_type": o.get("problem_type"),
        "explanation": o.get("explanation"),
        "potential_cancellation_risk": cancellation.get("flagged", False),
    }


def build_customer_impact_risks_table(orchestrator):
    risks, error = _safe(orchestrator.svc.cx_engine.get_customer_impact_risks)
    if risks is None:
        return pd.DataFrame(), error
    return pd.DataFrame([flatten_cx_order(o) for o in risks]), None


def build_at_risk_customer_orders_table(orchestrator, limit=10):
    orders, error = _safe(orchestrator.svc.cx_engine.get_at_risk_customer_orders, limit=limit)
    if orders is None:
        return pd.DataFrame(), error
    return pd.DataFrame([flatten_cx_order(o) for o in orders]), None


def build_service_recovery_recommendations(orchestrator):
    return _safe(orchestrator.svc.cx_engine.get_service_recovery_recommendations)


def build_customer_order_experience_detail(orchestrator, order_id):
    return _safe(orchestrator.svc.cx_engine.analyze_customer_order_experience, order_id)


# --------------------------------------------------------------------- #
# Ask Retail AI
# --------------------------------------------------------------------- #
def run_retail_query(orchestrator, query_text):
    """Routes through the existing RetailIntelligenceOrchestrator.handle_query --
    deterministic, no OpenAI API key involved, no duplicated routing logic."""
    if not isinstance(query_text, str) or not query_text.strip():
        return None, "Please enter a question."
    return _safe(orchestrator.handle_query, query_text)
