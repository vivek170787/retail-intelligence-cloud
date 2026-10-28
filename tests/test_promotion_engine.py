"""
Tests for promotion_agent/promotion_engine.py.

Uses the REAL InventoryRiskEngine and DemandForecastEngine (genuine
integration coverage) wired to a FakeRetailDataService with constructed
data, mirroring the fake-service pattern used throughout this project's
other agent test suites.
"""

import pandas as pd
import pytest

from promotion_agent.config import PromotionAnalysisSettings
from promotion_agent.promotion_engine import (
    PromotionIntelligenceEngine,
    READINESS_CANNOT_DETERMINE,
    READINESS_INSUFFICIENT,
    READINESS_SUFFICIENT,
    STATUS_ACTIVE,
    STATUS_EXPIRED,
    STATUS_UPCOMING,
    compare_window,
    compute_promo_uplift,
    find_overlapping_promotions,
    inbound_within_period,
    promotion_status,
)
from promotion_agent.llm_explainer import answer_question

SETTINGS = PromotionAnalysisSettings()

PRODUCTS_COLUMNS = ["sku", "product_name", "category", "brand", "selling_price", "cost_price"]
STORES_COLUMNS = ["store_id", "store_name", "city", "region", "store_type"]
SALES_COLUMNS = ["transaction_id", "transaction_date", "store_id", "sku", "quantity_sold", "selling_price", "sales_channel"]
INVENTORY_COLUMNS = ["sku", "location_id", "location_type", "on_hand_quantity", "reserved_quantity", "available_quantity", "last_updated"]
ORDERS_COLUMNS = ["order_id", "customer_id", "order_date", "sku", "quantity", "order_status", "fulfillment_location", "promised_delivery_date"]
WAREHOUSE_COLUMNS = ["warehouse_id", "sku", "on_hand_quantity", "reserved_quantity", "inbound_quantity", "supplier_lead_time_days"]
PROMOTIONS_COLUMNS = ["promotion_id", "sku", "promotion_name", "discount_percent", "start_date", "end_date", "promotion_channel"]


def _validate_sku(sku):
    if not isinstance(sku, str) or not sku.strip():
        raise ValueError(f"sku must be a non-empty string, got: {sku!r}")
    return sku.strip()


class FakeRetailDataService:
    def __init__(self, products=None, stores=None, sales=None, inventory=None,
                 orders=None, warehouse=None, promotions=None):
        self.products_df = products if products is not None else pd.DataFrame(columns=PRODUCTS_COLUMNS)
        self.stores_df = stores if stores is not None else pd.DataFrame(columns=STORES_COLUMNS)
        self.sales_df = sales if sales is not None else pd.DataFrame(columns=SALES_COLUMNS)
        self.inventory_df = inventory if inventory is not None else pd.DataFrame(columns=INVENTORY_COLUMNS)
        self.orders_df = orders if orders is not None else pd.DataFrame(columns=ORDERS_COLUMNS)
        self.warehouse_df = warehouse if warehouse is not None else pd.DataFrame(columns=WAREHOUSE_COLUMNS)
        self.promotions_df = promotions if promotions is not None else pd.DataFrame(columns=PROMOTIONS_COLUMNS)

    def get_products(self):
        return self.products_df

    def get_stores(self):
        return self.stores_df

    def get_sales(self):
        return self.sales_df

    def get_sales_by_sku(self, sku):
        sku = _validate_sku(sku)
        return self.sales_df[self.sales_df["sku"] == sku].reset_index(drop=True)

    def get_inventory(self):
        return self.inventory_df

    def get_inventory_by_sku(self, sku):
        sku = _validate_sku(sku)
        return self.inventory_df[self.inventory_df["sku"] == sku].reset_index(drop=True)

    def get_orders_by_sku(self, sku):
        sku = _validate_sku(sku)
        return self.orders_df[self.orders_df["sku"] == sku].reset_index(drop=True)

    def get_warehouse_stock(self, sku):
        sku = _validate_sku(sku)
        return self.warehouse_df[self.warehouse_df["sku"] == sku].reset_index(drop=True)

    def get_promotions(self, sku=None):
        if sku is None:
            return self.promotions_df
        sku = _validate_sku(sku)
        return self.promotions_df[self.promotions_df["sku"] == sku].reset_index(drop=True)


def _daily_sales_rows(sku, store_id, start_date, quantities):
    dates = pd.date_range(start_date, periods=len(quantities))
    return pd.DataFrame({
        "transaction_id": [f"TXN-{sku}-{i}" for i in range(len(quantities))],
        "transaction_date": dates, "store_id": store_id, "sku": sku,
        "quantity_sold": quantities, "selling_price": 10.0, "sales_channel": "in_store",
    })


def _promo_row(promotion_id, sku, start_date, end_date, discount_percent=20, channel="online"):
    return {
        "promotion_id": promotion_id, "sku": sku, "promotion_name": f"{discount_percent}% Off",
        "discount_percent": discount_percent,
        "start_date": pd.Timestamp(start_date), "end_date": pd.Timestamp(end_date),
        "promotion_channel": channel,
    }


def _build_fixture(sku="SKU-ABC-0001", store_id="ST-001", quantities=None,
                    store_available=10.0, warehouse_on_hand=100.0, warehouse_reserved=0.0,
                    warehouse_inbound=0.0, supplier_lead_time_days=3, promotions=None):
    quantities = quantities if quantities is not None else [10.0] * 60
    products = pd.DataFrame([{
        "sku": sku, "product_name": "Test Widget", "category": "Home",
        "brand": "TestBrand", "selling_price": 10.0, "cost_price": 5.0,
    }])
    stores = pd.DataFrame([{
        "store_id": store_id, "store_name": "Test Store", "city": "Testville",
        "region": "Test", "store_type": "Flagship",
    }])
    sales = _daily_sales_rows(sku, store_id, "2026-08-01", quantities)
    inventory = pd.DataFrame([{
        "sku": sku, "location_id": store_id, "location_type": "store",
        "on_hand_quantity": store_available, "reserved_quantity": 0,
        "available_quantity": store_available, "last_updated": "2026-10-27",
    }])
    orders = pd.DataFrame(columns=ORDERS_COLUMNS)
    warehouse = pd.DataFrame([{
        "warehouse_id": "WH-01", "sku": sku,
        "on_hand_quantity": warehouse_on_hand, "reserved_quantity": warehouse_reserved,
        "inbound_quantity": warehouse_inbound, "supplier_lead_time_days": supplier_lead_time_days,
    }])
    promotions_df = pd.DataFrame(promotions) if promotions else pd.DataFrame(columns=PROMOTIONS_COLUMNS)
    service = FakeRetailDataService(products, stores, sales, inventory, orders, warehouse, promotions_df)
    return service, sku, store_id


def _engine(service, settings=None):
    return PromotionIntelligenceEngine(service=service, settings=settings or SETTINGS)


# --------------------------------------------------------------------- #
# Pure functions
# --------------------------------------------------------------------- #
def test_promotion_status_upcoming_active_expired():
    ref = pd.Timestamp("2026-10-27")
    assert promotion_status(pd.Timestamp("2026-11-01"), pd.Timestamp("2026-11-05"), ref) == STATUS_UPCOMING
    assert promotion_status(pd.Timestamp("2026-10-20"), pd.Timestamp("2026-10-30"), ref) == STATUS_ACTIVE
    assert promotion_status(pd.Timestamp("2026-09-01"), pd.Timestamp("2026-09-10"), ref) == STATUS_EXPIRED


def test_find_overlapping_promotions():
    df = pd.DataFrame([
        _promo_row("P1", "SKU-A", "2026-10-01", "2026-10-10"),
        _promo_row("P2", "SKU-A", "2026-10-05", "2026-10-15"),  # overlaps P1
        _promo_row("P3", "SKU-B", "2026-10-01", "2026-10-10"),  # different sku, no overlap partner
    ])
    overlaps = find_overlapping_promotions(df)
    assert ("P1", "P2") in overlaps
    assert len(overlaps) == 1


def test_compare_window_zero_sales():
    series = pd.Series([0.0] * 10, index=pd.date_range("2026-10-01", periods=10))
    window = compare_window(series, "2026-10-01", "2026-10-05", min_days=3)
    assert window["total_units"] == 0.0
    assert window["avg_daily_units"] == 0.0
    assert window["fully_covered"] is True


def test_compute_promo_uplift_insufficient_coverage_returns_warning_not_number():
    promo_window = {"confirmed_days": 1, "fully_covered": False}
    baseline_window = {"confirmed_days": 5, "fully_covered": True}
    result = compute_promo_uplift(promo_window, baseline_window, False, SETTINGS)
    assert result["comparable"] is False
    assert result["observed_percent_change"] is None
    assert result["reason"] == "insufficient_or_incomplete_coverage_in_promo_or_baseline_window"


def test_compute_promo_uplift_baseline_overlap_blocks_comparison():
    promo_window = {"confirmed_days": 5, "fully_covered": True, "avg_daily_units": 10.0}
    baseline_window = {"confirmed_days": 5, "fully_covered": True, "avg_daily_units": 5.0}
    result = compute_promo_uplift(promo_window, baseline_window, True, SETTINGS)
    assert result["comparable"] is False
    assert result["reason"] == "baseline_window_overlaps_another_promotion_for_this_sku"


def test_compute_promo_uplift_computes_percent_change_when_comparable():
    promo_window = {"confirmed_days": 5, "fully_covered": True, "avg_daily_units": 15.0}
    baseline_window = {"confirmed_days": 5, "fully_covered": True, "avg_daily_units": 10.0}
    result = compute_promo_uplift(promo_window, baseline_window, False, SETTINGS)
    assert result["comparable"] is True
    assert result["observed_percent_change"] == 50.0
    assert "does not prove" in result["disclaimer"]


def test_inbound_within_period_excludes_long_lead_times():
    by_warehouse = [
        {"supplier_lead_time_days": 3, "inbound_quantity": 50.0},
        {"supplier_lead_time_days": 30, "inbound_quantity": 200.0},
        {"supplier_lead_time_days": None, "inbound_quantity": 10.0},
    ]
    within, unclear = inbound_within_period(by_warehouse, period_days=7)
    assert within == 50.0
    assert unclear == 210.0


# --------------------------------------------------------------------- #
# get_upcoming_promotions -- upcoming vs expired
# --------------------------------------------------------------------- #
def test_get_upcoming_promotions_excludes_expired_and_too_far_out():
    ref = pd.Timestamp("2026-10-27")
    promos = [
        _promo_row("P-EXPIRED", "SKU-ABC-0001", "2026-09-01", "2026-09-10"),
        _promo_row("P-UPCOMING", "SKU-ABC-0001", "2026-11-01", "2026-11-05"),
        _promo_row("P-TOO-FAR", "SKU-ABC-0001", "2026-12-01", "2026-12-05"),
    ]
    service, sku, _ = _build_fixture(promotions=promos)
    results = _engine(service).get_upcoming_promotions(days_ahead=14, reference_date=ref)
    ids = [r["promotion_id"] for r in results]
    assert ids == ["P-UPCOMING"]


def test_get_upcoming_promotions_days_ahead_validation():
    service, _, _ = _build_fixture()
    with pytest.raises(ValueError):
        _engine(service).get_upcoming_promotions(days_ahead=0)


# --------------------------------------------------------------------- #
# Missing promotion data / unknown SKU
# --------------------------------------------------------------------- #
def test_analyze_promotion_for_sku_no_promotion_history():
    service, sku, _ = _build_fixture(promotions=None)
    result = _engine(service).analyze_promotion_for_sku(sku)
    assert result["has_promotion_history"] is False
    assert result["promotions"] == []
    assert "Not every product has promotions" in result["note"]


def test_analyze_promotion_for_sku_unknown_sku_raises():
    service, _, _ = _build_fixture()
    with pytest.raises(ValueError):
        _engine(service).analyze_promotion_for_sku("")


# --------------------------------------------------------------------- #
# Missing / insufficient / sufficient inventory
# --------------------------------------------------------------------- #
def test_readiness_missing_inventory_resolves_to_zero_not_a_crash():
    # Consistent with InventoryRiskEngine's existing convention: no
    # inventory rows for a SKU resolves to 0 available (not None/unknown),
    # so with real forecasted demand this correctly becomes "insufficient".
    ref = pd.Timestamp("2026-10-20")
    promos = [_promo_row("P1", "SKU-ABC-0001", "2026-10-25", "2026-10-31")]
    sku = "SKU-ABC-0001"
    store_id = "ST-001"
    products = pd.DataFrame([{"sku": sku, "product_name": "W", "category": "Home", "brand": "X", "selling_price": 10.0, "cost_price": 5.0}])
    stores = pd.DataFrame([{"store_id": store_id, "store_name": "A", "city": "X", "region": "Y", "store_type": "Flagship"}])
    sales = _daily_sales_rows(sku, store_id, "2026-08-01", [10.0] * 60)
    service = FakeRetailDataService(products, stores, sales, promotions=pd.DataFrame(promos))  # no inventory rows
    result = _engine(service).analyze_promotion_for_sku(sku, reference_date=ref)
    report = result["readiness_reports"][0]
    assert report["observed"]["current_available_inventory"] == 0.0
    assert report["readiness_status"] == READINESS_INSUFFICIENT


def test_readiness_insufficient_inventory():
    ref = pd.Timestamp("2026-10-20")
    promos = [_promo_row("P1", "SKU-ABC-0001", "2026-10-25", "2026-10-31")]
    service, sku, _ = _build_fixture(quantities=[20.0] * 60, store_available=5.0, promotions=promos)
    result = _engine(service).analyze_promotion_for_sku(sku, reference_date=ref)
    report = result["readiness_reports"][0]
    assert report["readiness_status"] == READINESS_INSUFFICIENT
    assert report["demand_gap"] > 0
    assert any("replenish" in r.lower() or "warehouse" in r.lower() for r in report["recommendations"])


def test_readiness_sufficient_inventory():
    ref = pd.Timestamp("2026-10-20")
    promos = [_promo_row("P1", "SKU-ABC-0001", "2026-10-25", "2026-10-26")]  # short, 2-day promo
    service, sku, _ = _build_fixture(quantities=[1.0] * 60, store_available=1000.0, promotions=promos)
    result = _engine(service).analyze_promotion_for_sku(sku, reference_date=ref)
    report = result["readiness_reports"][0]
    assert report["readiness_status"] == READINESS_SUFFICIENT
    assert report["demand_gap"] <= 0


# --------------------------------------------------------------------- #
# Insufficient promotional history / zero sales in comparison window
# --------------------------------------------------------------------- #
def test_insufficient_promotional_history_not_comparable():
    # Only 1 day of sales history total -- nowhere near enough for a
    # fully-covered promo or baseline window.
    sku = "SKU-ABC-0001"
    store_id = "ST-001"
    products = pd.DataFrame([{"sku": sku, "product_name": "W", "category": "Home", "brand": "X", "selling_price": 10.0, "cost_price": 5.0}])
    stores = pd.DataFrame([{"store_id": store_id, "store_name": "A", "city": "X", "region": "Y", "store_type": "Flagship"}])
    sales = _daily_sales_rows(sku, store_id, "2026-10-05", [5.0])
    promos = [_promo_row("P1", sku, "2026-10-05", "2026-10-05")]
    service = FakeRetailDataService(products, stores, sales, promotions=pd.DataFrame(promos))
    result = _engine(service).compare_promotional_and_nonpromotional_sales(sku=sku)
    assert result["comparisons"][0]["comparable"] is False


def test_zero_sales_in_comparison_period_is_comparable_but_shows_zero():
    sku = "SKU-ABC-0001"
    store_id = "ST-001"
    products = pd.DataFrame([{"sku": sku, "product_name": "W", "category": "Home", "brand": "X", "selling_price": 10.0, "cost_price": 5.0}])
    stores = pd.DataFrame([{"store_id": store_id, "store_name": "A", "city": "X", "region": "Y", "store_type": "Flagship"}])
    # Zero sales everywhere (confirmed zero, not unknown) for 20 days, then a 5-day promo window.
    sales = _daily_sales_rows(sku, store_id, "2026-10-01", [0.0] * 20)
    promos = [_promo_row("P1", sku, "2026-10-16", "2026-10-20")]  # last 5 days of the 20
    service = FakeRetailDataService(products, stores, sales, promotions=pd.DataFrame(promos))
    result = _engine(service).compare_promotional_and_nonpromotional_sales(sku=sku)
    comparison = result["comparisons"][0]
    assert comparison["comparable"] is True
    assert comparison["observed_avg_daily_units_during_promotion"] == 0.0
    assert comparison["observed_percent_change"] is None  # zero baseline -> no ratio, not fabricated


# --------------------------------------------------------------------- #
# Overlapping promotions
# --------------------------------------------------------------------- #
def test_overlapping_promotions_flagged_and_baseline_blocked():
    sku = "SKU-ABC-0001"
    promos = [
        _promo_row("P1", sku, "2026-10-10", "2026-10-20"),
        _promo_row("P2", sku, "2026-10-15", "2026-10-25"),  # overlaps P1
    ]
    service, _, _ = _build_fixture(sku=sku, quantities=[10.0] * 90, promotions=promos)
    result = _engine(service).analyze_promotion_for_sku(sku, reference_date=pd.Timestamp("2026-10-01"))
    by_id = {p["promotion_id"]: p for p in result["promotions"]}
    assert by_id["P1"]["overlaps_another_promotion_for_this_sku"] is True
    assert by_id["P2"]["overlaps_another_promotion_for_this_sku"] is True


# --------------------------------------------------------------------- #
# Missing forecast data
# --------------------------------------------------------------------- #
def test_missing_forecast_data_insufficient_history():
    ref = pd.Timestamp("2026-10-20")
    promos = [_promo_row("P1", "SKU-ABC-0001", "2026-10-25", "2026-10-31")]
    service, sku, _ = _build_fixture(quantities=[5.0] * 3, store_available=100.0, promotions=promos)  # too little history
    result = _engine(service).analyze_promotion_for_sku(sku, reference_date=ref)
    report = result["readiness_reports"][0]
    assert report["baseline_forecast_demand"] is None
    assert report["readiness_status"] == READINESS_CANNOT_DETERMINE
    assert any("insufficient history" in w for w in report["data_quality_warnings"])


# --------------------------------------------------------------------- #
# Inbound stock arriving too late
# --------------------------------------------------------------------- #
def test_inbound_stock_arriving_too_late_is_excluded():
    ref = pd.Timestamp("2026-10-20")
    promos = [_promo_row("P1", "SKU-ABC-0001", "2026-10-25", "2026-10-26")]  # 2-day promo
    service, sku, _ = _build_fixture(
        quantities=[10.0] * 60, store_available=0.0,
        warehouse_inbound=500.0, supplier_lead_time_days=30,  # arrives long after the promo ends
        promotions=promos,
    )
    result = _engine(service).analyze_promotion_for_sku(sku, reference_date=ref)
    report = result["readiness_reports"][0]
    assert report["observed"]["known_inbound_stock_eligible_within_promotion"] == 0.0
    assert report["observed"]["known_inbound_stock_timing_unclear"] == 500.0
    assert report["readiness_status"] == READINESS_INSUFFICIENT


# --------------------------------------------------------------------- #
# Unknown uplift vs. user-supplied hypothetical uplift
# --------------------------------------------------------------------- #
def test_unknown_uplift_uses_baseline_only():
    ref = pd.Timestamp("2026-10-20")
    promos = [_promo_row("P1", "SKU-ABC-0001", "2026-10-25", "2026-10-31")]
    service, sku, _ = _build_fixture(quantities=[10.0] * 60, store_available=1000.0, promotions=promos)
    result = _engine(service).analyze_promotion_for_sku(sku, reference_date=ref)
    report = result["readiness_reports"][0]
    assert report["promotional_demand_estimate"]["source"] == "unknown"
    assert report["promotional_demand_estimate"]["estimated_total_demand"] is None
    assert any("unknown" in w.lower() for w in report["data_quality_warnings"])


def test_user_supplied_hypothetical_uplift_is_clearly_labeled_as_scenario():
    ref = pd.Timestamp("2026-10-20")
    promos = [_promo_row("P1", "SKU-ABC-0001", "2026-10-25", "2026-10-31")]
    service, sku, _ = _build_fixture(quantities=[10.0] * 60, store_available=1000.0, promotions=promos)
    result = _engine(service).analyze_promotion_for_sku(sku, reference_date=ref, assumed_uplift_pct=50.0)
    report = result["readiness_reports"][0]
    estimate = report["promotional_demand_estimate"]
    assert estimate["source"] == "assumed_scenario"
    assert estimate["uplift_pct_used"] == 50.0
    assert estimate["estimated_total_demand"] == pytest.approx(report["baseline_forecast_demand"] * 1.5)


def test_invalid_assumed_uplift_pct_raises():
    service, sku, _ = _build_fixture()
    with pytest.raises(ValueError):
        _engine(service).analyze_promotion_for_sku(sku, assumed_uplift_pct="fifty")


# --------------------------------------------------------------------- #
# Observed sales vs. simulated scenario -- correct distinction
# --------------------------------------------------------------------- #
def test_observed_history_and_assumed_scenario_are_never_conflated():
    ref = pd.Timestamp("2026-11-10")
    # A past, fully-comparable promotion with a real observed uplift...
    past_promo = _promo_row("P-PAST", "SKU-ABC-0001", "2026-10-01", "2026-10-05")
    # ...and a future promotion we evaluate with a user-supplied scenario.
    future_promo = _promo_row("P-FUTURE", "SKU-ABC-0001", "2026-11-15", "2026-11-19")
    # Sales start 2026-08-01; day 61 = 2026-10-01, day 65 = 2026-10-05 (the
    # promo window). Days 0-60 (including the Sep 26-30 baseline) are a
    # flat 10/day, and the promo window itself bumps to 20/day -> a clean,
    # fully-covered, exactly-100%-uplift comparison.
    quantities = [10.0] * 61 + [20.0] * 5
    service, sku, _ = _build_fixture(quantities=quantities, store_available=1000.0, promotions=[past_promo, future_promo])
    result = _engine(service).analyze_promotion_for_sku(sku, reference_date=ref, assumed_uplift_pct=5.0)

    past_entry = next(p for p in result["promotions"] if p["promotion_id"] == "P-PAST")
    assert past_entry["historical_comparison"]["comparable"] is True
    assert past_entry["historical_comparison"]["observed_percent_change"] == 100.0  # observed, real

    future_report = result["readiness_reports"][0]
    assert future_report["promotion_id"] == "P-FUTURE"
    assert future_report["promotional_demand_estimate"]["source"] == "assumed_scenario"
    assert future_report["promotional_demand_estimate"]["uplift_pct_used"] == 5.0  # the user's hypothetical, not the observed 100%


# --------------------------------------------------------------------- #
# OpenAI API unavailable
# --------------------------------------------------------------------- #
def test_answer_question_works_without_api_key(monkeypatch):
    promos = [_promo_row("P1", "SKU-ABC-0001", "2026-11-01", "2026-11-05")]
    service, sku, _ = _build_fixture(quantities=[10.0] * 60, promotions=promos)
    engine = _engine(service)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    result = answer_question(f"Is inventory sufficient for {sku}'s promotion?", engine=engine)
    assert result["configured"] is False
    assert result["answer"] is None
    assert "sku_analysis" in result["evidence"]
    assert "OPENAI_API_KEY" in result["message"]


# --------------------------------------------------------------------- #
# Catalog-wide resilience: one bad promotion must not abort the scan
# --------------------------------------------------------------------- #
class _SelectivelyFailingInventoryEngine:
    """Wraps a real InventoryRiskEngine but raises for one specific SKU --
    used to prove a single bad promotion/SKU can't abort a catalog-wide scan."""

    def __init__(self, real_engine, fail_sku):
        self.real_engine = real_engine
        self.fail_sku = fail_sku

    def get_product_inventory_analysis(self, sku):
        if sku == self.fail_sku:
            raise RuntimeError(f"simulated failure for {sku}")
        return self.real_engine.get_product_inventory_analysis(sku)


def test_catalog_wide_scan_isolates_one_failing_promotion():
    from inventory_agent.risk_engine import InventoryRiskEngine

    ref = pd.Timestamp("2026-10-20")
    good_sku, bad_sku = "SKU-ABC-0001", "SKU-XYZ-0002"
    promos = [
        _promo_row("P-GOOD", good_sku, "2026-10-25", "2026-10-31"),
        _promo_row("P-BAD", bad_sku, "2026-10-25", "2026-10-31"),
    ]
    products = pd.DataFrame([
        {"sku": good_sku, "product_name": "Good", "category": "Home", "brand": "X", "selling_price": 10.0, "cost_price": 5.0},
        {"sku": bad_sku, "product_name": "Bad", "category": "Home", "brand": "X", "selling_price": 10.0, "cost_price": 5.0},
    ])
    stores = pd.DataFrame([{"store_id": "ST-001", "store_name": "A", "city": "X", "region": "Y", "store_type": "Flagship"}])
    sales = pd.concat([
        _daily_sales_rows(good_sku, "ST-001", "2026-08-01", [10.0] * 90),
        _daily_sales_rows(bad_sku, "ST-001", "2026-08-01", [10.0] * 90),
    ], ignore_index=True)
    service = FakeRetailDataService(products, stores, sales, promotions=pd.DataFrame(promos))

    real_inventory = InventoryRiskEngine(service=service)
    failing_inventory = _SelectivelyFailingInventoryEngine(real_inventory, fail_sku=bad_sku)
    engine = PromotionIntelligenceEngine(service=service, settings=SETTINGS, inventory_engine=failing_inventory)

    report = engine.get_promotion_readiness_report(reference_date=ref)
    assert report["total_promotions_assessed"] == 2
    by_sku = {r["sku"]: r for r in report["reports"]}
    assert by_sku[good_sku].get("error") is None
    assert by_sku[bad_sku].get("error") is not None
    assert by_sku[bad_sku]["readiness_status"] == READINESS_CANNOT_DETERMINE


# --------------------------------------------------------------------- #
# Promotional demand summary / registration smoke test
# --------------------------------------------------------------------- #
def test_promotional_demand_summary_counts_skus_without_history():
    sku_with = "SKU-ABC-0001"
    sku_without = "SKU-XYZ-0002"
    products = pd.DataFrame([
        {"sku": sku_with, "product_name": "A", "category": "Home", "brand": "X", "selling_price": 10.0, "cost_price": 5.0},
        {"sku": sku_without, "product_name": "B", "category": "Home", "brand": "X", "selling_price": 10.0, "cost_price": 5.0},
    ])
    stores = pd.DataFrame([{"store_id": "ST-001", "store_name": "A", "city": "X", "region": "Y", "store_type": "Flagship"}])
    sales = pd.concat([
        _daily_sales_rows(sku_with, "ST-001", "2026-08-01", [10.0] * 60),
        _daily_sales_rows(sku_without, "ST-001", "2026-08-01", [10.0] * 60),
    ], ignore_index=True)
    promos = [_promo_row("P1", sku_with, "2026-11-01", "2026-11-05")]
    service = FakeRetailDataService(products, stores, sales, promotions=pd.DataFrame(promos))

    summary = _engine(service).get_promotional_demand_summary(reference_date=pd.Timestamp("2026-10-20"))
    assert summary["products_with_any_promotion_history"] == 1
    assert summary["products_with_no_promotion_history"] == 1


def test_default_engine_registered_with_orchestration():
    from orchestration.service import RetailOrchestrationService
    orchestrator = RetailOrchestrationService()
    assert orchestrator.promotion_engine.service is orchestrator.service
    assert orchestrator.promotion_engine.inventory_engine is orchestrator.inventory_engine
    assert orchestrator.promotion_engine.demand_engine is orchestrator.demand_engine


def test_default_engine_runs_end_to_end_against_real_data():
    from promotion_agent.promotion_engine import get_promotional_demand_summary
    summary = get_promotional_demand_summary()
    assert summary["total_products"] > 0
    assert summary["products_with_any_promotion_history"] <= summary["total_products"]
