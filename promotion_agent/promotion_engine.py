"""
Deterministic promotion analysis for the Promotion Intelligence Agent.

Reuses the existing agents' public interfaces directly -- no duplicated
data access or forecasting math:
  - RetailDataService.get_promotions() / get_sales_by_sku() / get_sales() / etc.
  - DemandForecastEngine.forecast_demand(sku, horizon_days) for baseline demand
  - InventoryRiskEngine.get_product_inventory_analysis(sku) for current inventory
  - demand_forecasting_agent's pure dedupe/clean/zero-fill functions, for the
    EXACT same confirmed-coverage daily series used in historical sales
    comparisons as the Demand Forecasting Agent itself uses.

Promotions in this dataset are scoped by SKU and promotion_channel (e.g.
"in_store", "online") -- there is no per-store promotion field, so this
agent never assumes or invents store-level promotion targeting. Not every
product has promotion history (confirmed: only 26 of 60 SKUs in this
dataset have any), so every per-SKU function handles the no-history case
explicitly rather than assuming one exists.

Promotional uplift is NEVER invented. It is either:
  - computed from an actual, sufficiently-covered historical promotion for
    that SKU (source="historical_uplift"), or
  - supplied explicitly by the caller as a what-if scenario
    (source="assumed_scenario"), or
  - left unknown (source="unknown"), in which case only the baseline
    (non-promotional) demand forecast is used for readiness assessment.

All recommendations are read-only text for human review -- this module
never activates a promotion, changes a price, places an order, or
transfers inventory.
"""

import pandas as pd

from services.retail_data_service import RetailDataService
from inventory_agent.risk_engine import InventoryRiskEngine
from demand_forecasting_agent.forecasting_engine import (
    DemandForecastEngine,
    build_daily_series,
    clean_quantities,
    dedupe_transactions,
    global_confirmed_dates,
)
from promotion_agent.config import PromotionAnalysisSettings

STATUS_UPCOMING = "upcoming"
STATUS_ACTIVE = "active"
STATUS_EXPIRED = "expired"

READINESS_SUFFICIENT = "sufficient"
READINESS_INSUFFICIENT = "insufficient"
READINESS_CANNOT_DETERMINE = "cannot_determine"

DISCLAIMER = (
    "All recommendations are read-only and require human approval. No "
    "promotion is activated, no price is changed, no order is placed, and "
    "no inventory is transferred automatically."
)

UPLIFT_DISCLAIMER = (
    "This reflects an observed sales difference between the promotional "
    "period and the immediately preceding comparable period. It does not "
    "prove the promotion caused the difference -- other factors (seasonality, "
    "other concurrent events, random variation) may also contribute."
)


# --------------------------------------------------------------------- #
# Pure functions -- no I/O
# --------------------------------------------------------------------- #
def promotion_status(start_date, end_date, reference_date):
    if end_date < reference_date:
        return STATUS_EXPIRED
    if start_date <= reference_date <= end_date:
        return STATUS_ACTIVE
    return STATUS_UPCOMING


def find_overlapping_promotions(promotions_df):
    """Return [(promotion_id_a, promotion_id_b), ...] for same-SKU
    promotions whose date ranges overlap -- relevant because an uplift
    measured during one can't cleanly be attributed to it alone."""
    overlaps = []
    if promotions_df is None or len(promotions_df) == 0:
        return overlaps
    for _, group in promotions_df.groupby("sku"):
        rows = group.sort_values("start_date").to_dict("records")
        for i in range(len(rows)):
            for j in range(i + 1, len(rows)):
                a, b = rows[i], rows[j]
                if a["start_date"] <= b["end_date"] and b["start_date"] <= a["end_date"]:
                    overlaps.append((a["promotion_id"], b["promotion_id"]))
    return overlaps


def sku_daily_sales_series(service, sku):
    """Builds the confirmed-coverage daily sales series for one SKU using
    the EXACT SAME pure functions as demand_forecasting_agent -- dedupe,
    clean invalid quantities, and zero-fill only dates the overall system
    is confirmed to have been operating on. Returns
    (series, unknown_coverage_days, invalid_qty_count)."""
    sales_df = service.get_sales_by_sku(sku)  # validates sku
    all_sales = service.get_sales()

    sales_df = dedupe_transactions(sales_df)
    sales_df, invalid_qty_count = clean_quantities(sales_df)
    all_sales = dedupe_transactions(all_sales)
    all_sales, _ = clean_quantities(all_sales)

    confirmed_dates = global_confirmed_dates(all_sales)
    series, unknown_coverage_days = build_daily_series(sales_df, confirmed_dates)
    return series, unknown_coverage_days, invalid_qty_count


def compare_window(series, window_start, window_end, min_days):
    """Confirmed-only sum/average over [window_start, window_end]. Never
    fabricates missing days -- `fully_covered` tells the caller whether
    every expected day actually had confirmed data."""
    window_start = pd.Timestamp(window_start)
    window_end = pd.Timestamp(window_end)
    expected_days = (window_end - window_start).days + 1

    if series is None or len(series) == 0:
        window_series = pd.Series(dtype=float)
    else:
        window_series = series.loc[(series.index >= window_start) & (series.index <= window_end)]

    confirmed_days = len(window_series)
    return {
        "start": str(window_start.date()),
        "end": str(window_end.date()),
        "expected_days": expected_days,
        "confirmed_days": confirmed_days,
        "total_units": float(window_series.sum()) if confirmed_days else None,
        "avg_daily_units": float(window_series.mean()) if confirmed_days else None,
        "fully_covered": confirmed_days == expected_days,
    }


def compute_promo_uplift(promo_window, baseline_window, baseline_overlaps_other_promo, settings):
    """Compare a promotional window against the immediately preceding,
    same-length baseline window. Returns comparable=False with an explicit
    reason whenever the comparison can't be trusted -- never fabricates
    an uplift number from insufficient or contaminated data."""
    if baseline_overlaps_other_promo:
        return {
            "comparable": False,
            "reason": "baseline_window_overlaps_another_promotion_for_this_sku",
            "promo_period": promo_window, "baseline_period": baseline_window,
            "observed_sales_difference": None, "observed_percent_change": None,
        }

    if (
        promo_window["confirmed_days"] < settings.min_comparison_days
        or baseline_window["confirmed_days"] < settings.min_comparison_days
        or not promo_window["fully_covered"]
        or not baseline_window["fully_covered"]
    ):
        return {
            "comparable": False,
            "reason": "insufficient_or_incomplete_coverage_in_promo_or_baseline_window",
            "promo_period": promo_window, "baseline_period": baseline_window,
            "observed_sales_difference": None, "observed_percent_change": None,
        }

    promo_avg = promo_window["avg_daily_units"]
    baseline_avg = baseline_window["avg_daily_units"]
    difference = promo_avg - baseline_avg
    percent_change = None if baseline_avg <= 0 else (difference / baseline_avg) * 100

    return {
        "comparable": True,
        "reason": None,
        "promo_period": promo_window, "baseline_period": baseline_window,
        "observed_avg_daily_units_during_promotion": round(promo_avg, 2),
        "observed_avg_daily_units_baseline": round(baseline_avg, 2),
        "observed_sales_difference": round(difference, 2),
        "observed_percent_change": round(percent_change, 1) if percent_change is not None else None,
        "disclaimer": UPLIFT_DISCLAIMER,
    }


def inbound_within_period(by_warehouse, period_days):
    """Only count inbound stock as usable supply for a given period when
    its supplier lead time is known AND falls within that period --
    mirrors orchestration/service.py's inbound-timing logic, applied here
    against a promotion's own duration rather than a forecast horizon.
    (Small intentional duplication, documented: promotion_agent must not
    import orchestration, since orchestration imports promotion_agent to
    register it -- importing back would be circular.)"""
    if not by_warehouse:
        return 0.0, 0.0
    within = 0.0
    unclear = 0.0
    for row in by_warehouse:
        lead_time = row["supplier_lead_time_days"]
        if lead_time is not None and lead_time <= period_days:
            within += row["inbound_quantity"]
        else:
            unclear += row["inbound_quantity"]
    return within, unclear


def build_recommendations(readiness_status, days_until_start, max_known_lead_time, inventory_risk_level, promo_status_value):
    """Deterministic, read-only recommendation strings. Never an action --
    always phrased as something for a human to investigate or review."""
    recs = []
    if readiness_status == READINESS_INSUFFICIENT:
        if max_known_lead_time is not None and days_until_start < max_known_lead_time:
            recs.append(
                "Check warehouse availability -- supplier lead time may exceed "
                "the time remaining before the promotion starts."
            )
        else:
            recs.append("Investigate replenishment before the promotion starts.")
        recs.append("Consider reviewing the promotion if supply constraints cannot be resolved.")
    elif readiness_status == READINESS_CANNOT_DETERMINE:
        recs.append("Review promotion readiness manually -- insufficient data to assess automatically.")

    if inventory_risk_level in ("critical", "high"):
        recs.append("Review promotion readiness for a high-risk SKU.")

    if promo_status_value in (STATUS_UPCOMING, STATUS_ACTIVE):
        recs.append("Monitor demand daily during the promotion.")

    return recs


# --------------------------------------------------------------------- #
# Data-orchestration layer
# --------------------------------------------------------------------- #
class PromotionIntelligenceEngine:
    def __init__(self, service=None, settings=None, inventory_engine=None, demand_engine=None):
        self.service = service if service is not None else RetailDataService()
        self.settings = settings if settings is not None else PromotionAnalysisSettings.from_env()
        self.inventory_engine = (
            inventory_engine if inventory_engine is not None
            else InventoryRiskEngine(service=self.service)
        )
        self.demand_engine = (
            demand_engine if demand_engine is not None
            else DemandForecastEngine(service=self.service, inventory_engine=self.inventory_engine)
        )

    # ---- shared helpers -------------------------------------------------
    def _reference_date(self, reference_date=None):
        return pd.Timestamp(reference_date).normalize() if reference_date is not None else pd.Timestamp.now().normalize()

    def _all_promotions(self):
        return self.service.get_promotions()  # bulk (sku=None)

    def _readiness_for_promotion(self, sku, promo, reference_date, historical_uplift, assumed_uplift_pct):
        duration_days = (promo["end_date"] - promo["start_date"]).days + 1
        days_until_start = max(0, (promo["start_date"] - reference_date).days)

        warnings = []
        forecast = None
        try:
            forecast = self.demand_engine.forecast_demand(sku, horizon_days=duration_days)
        except ValueError as exc:
            warnings.append(f"Demand Forecasting Agent error: {exc}")

        inventory = None
        try:
            inventory = self.inventory_engine.get_product_inventory_analysis(sku)
        except ValueError as exc:
            warnings.append(f"Inventory Intelligence Agent error: {exc}")

        baseline_demand = None
        if forecast is not None:
            if forecast["sufficient_data"]:
                baseline_demand = forecast["total_forecast_demand"]
            else:
                warnings.append("Baseline demand forecast unavailable (insufficient history).")

        uplift_source = "unknown"
        uplift_pct_used = None
        if assumed_uplift_pct is not None:
            uplift_source = "assumed_scenario"
            uplift_pct_used = assumed_uplift_pct
        elif historical_uplift and historical_uplift.get("comparable") and historical_uplift.get("observed_percent_change") is not None:
            uplift_source = "historical_uplift"
            uplift_pct_used = historical_uplift["observed_percent_change"]

        estimated_promotional_demand = None
        if baseline_demand is not None:
            if uplift_pct_used is not None:
                estimated_promotional_demand = round(baseline_demand * (1 + uplift_pct_used / 100), 2)
            else:
                warnings.append(
                    "Promotional uplift is unknown (no reliable historical comparison "
                    "and no scenario assumption supplied); only the baseline forecast is used."
                )

        current_available = inventory["observed"]["store_available_inventory"] if inventory else None
        by_warehouse = inventory["observed"]["warehouse"]["by_warehouse"] if inventory else []
        warehouse_available = inventory["observed"]["warehouse"]["warehouse_available"] if inventory else None
        eligible_inbound, unclear_inbound = inbound_within_period(by_warehouse, duration_days)
        if unclear_inbound > 0:
            warnings.append(
                f"{unclear_inbound:g} unit(s) of inbound stock have an unknown or "
                f"longer-than-promotion supplier lead time and were excluded as usable supply."
            )

        demand_for_readiness = estimated_promotional_demand if estimated_promotional_demand is not None else baseline_demand
        total_supply = (current_available + eligible_inbound) if current_available is not None else None

        if demand_for_readiness is None or current_available is None:
            readiness_status = READINESS_CANNOT_DETERMINE
        elif total_supply >= demand_for_readiness:
            readiness_status = READINESS_SUFFICIENT
        else:
            readiness_status = READINESS_INSUFFICIENT

        gap = (
            round(demand_for_readiness - total_supply, 2)
            if demand_for_readiness is not None and total_supply is not None
            else None
        )

        lead_times = [row["supplier_lead_time_days"] for row in by_warehouse if row["supplier_lead_time_days"] is not None]
        max_known_lead_time = max(lead_times) if lead_times else None
        status_value = promotion_status(promo["start_date"], promo["end_date"], reference_date)

        return {
            "promotion_id": promo["promotion_id"],
            "sku": sku,
            "status": status_value,
            "start_date": str(pd.Timestamp(promo["start_date"]).date()),
            "end_date": str(pd.Timestamp(promo["end_date"]).date()),
            "duration_days": duration_days,
            "days_until_start": days_until_start,
            "observed": {
                "current_available_inventory": current_available,
                "known_inbound_stock_eligible_within_promotion": eligible_inbound,
                "known_inbound_stock_timing_unclear": unclear_inbound,
                "warehouse_available_stock": warehouse_available,
                "max_known_supplier_lead_time_days": max_known_lead_time,
            },
            "baseline_forecast_demand": baseline_demand,
            "promotional_demand_estimate": {
                "source": uplift_source,
                "uplift_pct_used": uplift_pct_used,
                "estimated_total_demand": estimated_promotional_demand,
            },
            "demand_gap": gap,
            "readiness_status": readiness_status,
            "inventory_agent_risk_level": inventory["estimated"]["risk_level"] if inventory else None,
            "recommendations": build_recommendations(
                readiness_status, days_until_start, max_known_lead_time,
                inventory["estimated"]["risk_level"] if inventory else None,
                status_value,
            ),
            "data_quality_warnings": warnings,
            "disclaimer": DISCLAIMER,
        }

    def _relevant_promotions(self, days_ahead, reference_date):
        days_ahead = self.settings.default_days_ahead if days_ahead is None else days_ahead
        promos = self._all_promotions()
        if len(promos) == 0:
            return promos
        window_end = reference_date + pd.Timedelta(days=days_ahead)
        mask = (promos["end_date"] >= reference_date) & (promos["start_date"] <= window_end)
        return promos[mask]

    def _all_readiness_reports(self, days_ahead=None, reference_date=None, assumed_uplift_pct=None):
        relevant = self._relevant_promotions(days_ahead, reference_date)
        reports = []
        for _, promo_row in relevant.sort_values("start_date").iterrows():
            sku = promo_row["sku"]
            promo = promo_row.to_dict()
            try:
                series, _, _ = sku_daily_sales_series(self.service, sku)
                promos_for_sku = self.service.get_promotions(sku)
                other_promos = promos_for_sku[promos_for_sku["promotion_id"] != promo["promotion_id"]].to_dict("records")
                duration_days = (promo["end_date"] - promo["start_date"]).days + 1
                baseline_start = promo["start_date"] - pd.Timedelta(days=duration_days)
                baseline_end = promo["start_date"] - pd.Timedelta(days=1)
                promo_window = compare_window(series, promo["start_date"], promo["end_date"], self.settings.min_comparison_days)
                baseline_window = compare_window(series, baseline_start, baseline_end, self.settings.min_comparison_days)
                baseline_overlap = any(
                    p["start_date"] <= baseline_end and p["end_date"] >= baseline_start for p in other_promos
                )
                uplift = compute_promo_uplift(promo_window, baseline_window, baseline_overlap, self.settings)
                report = self._readiness_for_promotion(sku, promo, reference_date, uplift, assumed_uplift_pct)
            except Exception as exc:
                # A single problematic promotion/SKU must not abort the whole scan.
                report = {
                    "promotion_id": promo["promotion_id"], "sku": sku,
                    "readiness_status": READINESS_CANNOT_DETERMINE,
                    "error": f"{type(exc).__name__}: {exc}",
                    "days_until_start": max(0, (promo["start_date"] - reference_date).days),
                    "demand_gap": None,
                    "data_quality_warnings": [f"Unexpected error analyzing promotion for {sku!r}: {exc}"],
                }
            reports.append(report)
        return reports

    # ---- required public functions -------------------------------------
    def get_upcoming_promotions(self, days_ahead=None, reference_date=None):
        """Promotions that have NOT yet started, starting within
        `days_ahead` days of `reference_date` (defaults to now)."""
        days_ahead = self.settings.default_days_ahead if days_ahead is None else days_ahead
        if not isinstance(days_ahead, int) or isinstance(days_ahead, bool) or days_ahead <= 0:
            raise ValueError(f"days_ahead must be a positive integer, got: {days_ahead!r}")

        reference_date = self._reference_date(reference_date)
        window_end = reference_date + pd.Timedelta(days=days_ahead)

        promos = self._all_promotions()
        if len(promos) == 0:
            return []

        products_df = self.service.get_products()
        product_name_map = dict(zip(products_df["sku"], products_df["product_name"]))

        upcoming = promos[(promos["start_date"] > reference_date) & (promos["start_date"] <= window_end)]
        results = []
        for _, row in upcoming.sort_values("start_date").iterrows():
            results.append({
                "promotion_id": row["promotion_id"],
                "sku": row["sku"],
                "product_name": product_name_map.get(row["sku"], "Unknown product"),
                "promotion_name": row["promotion_name"],
                "discount_percent": row["discount_percent"],
                "start_date": str(row["start_date"].date()),
                "end_date": str(row["end_date"].date()),
                "promotion_channel": row["promotion_channel"],
                "days_until_start": (row["start_date"] - reference_date).days,
                "duration_days": (row["end_date"] - row["start_date"]).days + 1,
            })
        return results

    def analyze_promotion_for_sku(self, sku, reference_date=None, assumed_uplift_pct=None):
        """Full promotion history, overlap flags, historical comparisons,
        and readiness assessment(s) for a single SKU."""
        if assumed_uplift_pct is not None and not isinstance(assumed_uplift_pct, (int, float)):
            raise ValueError(f"assumed_uplift_pct must be a number, got: {assumed_uplift_pct!r}")
        if isinstance(assumed_uplift_pct, bool):
            raise ValueError(f"assumed_uplift_pct must be a number, got: {assumed_uplift_pct!r}")

        promos_df = self.service.get_promotions(sku)  # validates sku
        reference_date = self._reference_date(reference_date)

        products_df = self.service.get_products()
        product_rows = products_df[products_df["sku"] == sku]
        product_found = len(product_rows) > 0
        product_name = product_rows.iloc[0]["product_name"] if product_found else None

        if len(promos_df) == 0:
            return {
                "sku": sku, "product_found": product_found, "product_name": product_name,
                "has_promotion_history": False,
                "promotions": [],
                "readiness_reports": [],
                "note": f"No promotion history found for SKU {sku!r}. Not every product has promotions.",
            }

        series, unknown_coverage_days, invalid_qty_count = sku_daily_sales_series(self.service, sku)
        promo_records = promos_df.sort_values("start_date").to_dict("records")
        overlapping_ids = find_overlapping_promotions(promos_df)
        overlapping_id_set = {pid for pair in overlapping_ids for pid in pair}

        annotated = []
        readiness_reports = []
        for promo in promo_records:
            status_value = promotion_status(promo["start_date"], promo["end_date"], reference_date)

            duration_days = (promo["end_date"] - promo["start_date"]).days + 1
            baseline_start = promo["start_date"] - pd.Timedelta(days=duration_days)
            baseline_end = promo["start_date"] - pd.Timedelta(days=1)
            promo_window = compare_window(series, promo["start_date"], promo["end_date"], self.settings.min_comparison_days)
            baseline_window = compare_window(series, baseline_start, baseline_end, self.settings.min_comparison_days)

            other_promos = [p for p in promo_records if p["promotion_id"] != promo["promotion_id"]]
            baseline_overlap = any(
                p["start_date"] <= baseline_end and p["end_date"] >= baseline_start for p in other_promos
            )
            uplift = compute_promo_uplift(promo_window, baseline_window, baseline_overlap, self.settings)

            annotated.append({
                "promotion_id": promo["promotion_id"],
                "promotion_name": promo["promotion_name"],
                "discount_percent": promo["discount_percent"],
                "start_date": str(promo["start_date"].date()),
                "end_date": str(promo["end_date"].date()),
                "promotion_channel": promo["promotion_channel"],
                "status": status_value,
                "overlaps_another_promotion_for_this_sku": promo["promotion_id"] in overlapping_id_set,
                "historical_comparison": uplift,
            })

            if status_value in (STATUS_UPCOMING, STATUS_ACTIVE):
                readiness_reports.append(
                    self._readiness_for_promotion(sku, promo, reference_date, uplift, assumed_uplift_pct)
                )

        warnings = []
        if unknown_coverage_days:
            warnings.append(f"{unknown_coverage_days} day(s) of unknown sales coverage for this SKU.")
        if invalid_qty_count:
            warnings.append(f"{invalid_qty_count} invalid sales record(s) excluded.")

        return {
            "sku": sku, "product_found": product_found, "product_name": product_name,
            "has_promotion_history": True,
            "promotions": annotated,
            "readiness_reports": readiness_reports,
            "data_quality_warnings": warnings,
        }

    def get_promotions_with_inventory_risk(self, days_ahead=None, reference_date=None):
        """Upcoming/active promotions flagged insufficient OR undeterminable."""
        reference_date = self._reference_date(reference_date)
        reports = self._all_readiness_reports(days_ahead=days_ahead, reference_date=reference_date)
        flagged = [r for r in reports if r.get("readiness_status") in (READINESS_INSUFFICIENT, READINESS_CANNOT_DETERMINE)]
        flagged.sort(key=lambda r: (r.get("readiness_status") != READINESS_INSUFFICIENT, r.get("days_until_start", 0)))
        return flagged

    def get_promotional_demand_summary(self, days_ahead=None, reference_date=None):
        reference_date = self._reference_date(reference_date)
        products_df = self.service.get_products()
        all_promos = self._all_promotions()
        skus_with_history = set(all_promos["sku"]) if len(all_promos) else set()
        reports = self._all_readiness_reports(days_ahead=days_ahead, reference_date=reference_date)

        readiness_counts = {READINESS_SUFFICIENT: 0, READINESS_INSUFFICIENT: 0, READINESS_CANNOT_DETERMINE: 0}
        uplift_known_count = 0
        uplift_unknown_count = 0
        for r in reports:
            status_value = r.get("readiness_status", READINESS_CANNOT_DETERMINE)
            readiness_counts[status_value] = readiness_counts.get(status_value, 0) + 1
            source = (r.get("promotional_demand_estimate") or {}).get("source")
            if source == "historical_uplift":
                uplift_known_count += 1
            elif source in ("unknown", None):
                uplift_unknown_count += 1

        return {
            "data_as_of": str(reference_date.date()),
            "days_ahead": self.settings.default_days_ahead if days_ahead is None else days_ahead,
            "total_products": len(products_df),
            "products_with_any_promotion_history": len(skus_with_history),
            "products_with_no_promotion_history": len(products_df) - len(skus_with_history),
            "upcoming_or_active_promotions_in_window": len(reports),
            "readiness_counts": readiness_counts,
            "promotions_with_known_historical_uplift": uplift_known_count,
            "promotions_with_unknown_uplift": uplift_unknown_count,
            "settings_used": self.settings.as_dict(),
        }

    def get_promotion_stockout_risks(self, days_ahead=None, reference_date=None):
        """Strictly insufficient-inventory promotions only (a stricter
        subset of get_promotions_with_inventory_risk, which also includes
        cannot_determine cases)."""
        reference_date = self._reference_date(reference_date)
        reports = self._all_readiness_reports(days_ahead=days_ahead, reference_date=reference_date)
        at_risk = [r for r in reports if r.get("readiness_status") == READINESS_INSUFFICIENT]
        at_risk.sort(key=lambda r: (r.get("demand_gap") is None, -(r.get("demand_gap") or 0)))
        return at_risk

    def compare_promotional_and_nonpromotional_sales(self, sku=None):
        if sku is not None:
            promos_df = self.service.get_promotions(sku)  # validates sku
            if len(promos_df) == 0:
                return {
                    "sku": sku, "has_promotion_history": False,
                    "comparisons": [],
                    "note": f"No promotion history found for SKU {sku!r}.",
                }

            series, unknown_coverage_days, invalid_qty_count = sku_daily_sales_series(self.service, sku)
            promo_records = promos_df.sort_values("start_date").to_dict("records")
            comparisons = []
            for promo in promo_records:
                other_promos = [p for p in promo_records if p["promotion_id"] != promo["promotion_id"]]
                duration_days = (promo["end_date"] - promo["start_date"]).days + 1
                baseline_start = promo["start_date"] - pd.Timedelta(days=duration_days)
                baseline_end = promo["start_date"] - pd.Timedelta(days=1)
                promo_window = compare_window(series, promo["start_date"], promo["end_date"], self.settings.min_comparison_days)
                baseline_window = compare_window(series, baseline_start, baseline_end, self.settings.min_comparison_days)
                baseline_overlap = any(
                    p["start_date"] <= baseline_end and p["end_date"] >= baseline_start for p in other_promos
                )
                uplift = compute_promo_uplift(promo_window, baseline_window, baseline_overlap, self.settings)
                comparisons.append({
                    "promotion_id": promo["promotion_id"],
                    "promotion_name": promo["promotion_name"],
                    **uplift,
                })

            warnings = []
            if unknown_coverage_days:
                warnings.append(f"{unknown_coverage_days} day(s) of unknown sales coverage.")
            if invalid_qty_count:
                warnings.append(f"{invalid_qty_count} invalid sales record(s) excluded.")

            return {
                "sku": sku, "has_promotion_history": True,
                "comparisons": comparisons,
                "data_quality_warnings": warnings,
            }

        all_promos = self._all_promotions()
        total_products = len(self.service.get_products())
        if len(all_promos) == 0:
            return {
                "skus_with_promotion_history": 0,
                "skus_without_promotion_history": total_products,
                "comparable_promotions": 0, "not_comparable_promotions": 0,
                "average_observed_percent_change": None, "per_sku": [],
            }

        skus_with_history = sorted(all_promos["sku"].unique())
        per_sku = [self.compare_promotional_and_nonpromotional_sales(sku=s) for s in skus_with_history]

        all_comparisons = [c for r in per_sku for c in r["comparisons"]]
        comparable = [c for c in all_comparisons if c["comparable"]]
        not_comparable = [c for c in all_comparisons if not c["comparable"]]
        pct_changes = [c["observed_percent_change"] for c in comparable if c["observed_percent_change"] is not None]

        return {
            "skus_with_promotion_history": len(skus_with_history),
            "skus_without_promotion_history": total_products - len(skus_with_history),
            "comparable_promotions": len(comparable),
            "not_comparable_promotions": len(not_comparable),
            "average_observed_percent_change": round(sum(pct_changes) / len(pct_changes), 1) if pct_changes else None,
            "per_sku": per_sku,
        }

    def get_promotion_readiness_report(self, days_ahead=None, reference_date=None, assumed_uplift_pct=None):
        reference_date = self._reference_date(reference_date)
        reports = self._all_readiness_reports(
            days_ahead=days_ahead, reference_date=reference_date, assumed_uplift_pct=assumed_uplift_pct
        )
        reports.sort(key=lambda r: (r.get("readiness_status") != READINESS_INSUFFICIENT, r.get("days_until_start", 0)))
        return {
            "data_as_of": str(reference_date.date()),
            "days_ahead": self.settings.default_days_ahead if days_ahead is None else days_ahead,
            "total_promotions_assessed": len(reports),
            "reports": reports,
        }


_default_engine = PromotionIntelligenceEngine()


def get_upcoming_promotions(days_ahead=14):
    return _default_engine.get_upcoming_promotions(days_ahead=days_ahead)


def analyze_promotion_for_sku(sku, assumed_uplift_pct=None):
    return _default_engine.analyze_promotion_for_sku(sku, assumed_uplift_pct=assumed_uplift_pct)


def get_promotions_with_inventory_risk(days_ahead=None):
    return _default_engine.get_promotions_with_inventory_risk(days_ahead=days_ahead)


def get_promotional_demand_summary(days_ahead=None):
    return _default_engine.get_promotional_demand_summary(days_ahead=days_ahead)


def get_promotion_stockout_risks(days_ahead=None):
    return _default_engine.get_promotion_stockout_risks(days_ahead=days_ahead)


def compare_promotional_and_nonpromotional_sales(sku=None):
    return _default_engine.compare_promotional_and_nonpromotional_sales(sku=sku)


def get_promotion_readiness_report(days_ahead=None, assumed_uplift_pct=None):
    return _default_engine.get_promotion_readiness_report(days_ahead=days_ahead, assumed_uplift_pct=assumed_uplift_pct)
