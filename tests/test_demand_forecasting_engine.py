"""
Tests for demand_forecasting_agent/forecasting_engine.py.

Section A tests the pure statistical functions directly with constructed
inputs -- no data layer, no I/O.

Section B tests DemandForecastEngine's orchestration using a lightweight
FakeRetailDataService (mirrors RetailDataService's method surface and
sku-validation convention, same pattern as test_inventory_risk_engine.py)
and a FakeInventoryEngine stand-in for InventoryRiskEngine, so edge cases
can be constructed precisely without touching the real CSVs.

Section C is a light end-to-end smoke test against the real project data.
"""

import pandas as pd
import pytest

from demand_forecasting_agent.config import DemandForecastSettings
from demand_forecasting_agent.forecasting_engine import (
    DemandForecastEngine,
    backtest,
    build_daily_series,
    clean_quantities,
    dedupe_transactions,
    detect_change,
    forecast_core,
    get_demand_summary,
    global_confirmed_dates,
    seasonal_naive_forecast,
    weighted_moving_average,
)

SETTINGS = DemandForecastSettings()


# --------------------------------------------------------------------- #
# Section A: pure statistical functions
# --------------------------------------------------------------------- #
def test_dedupe_transactions_drops_duplicate_transaction_ids():
    df = pd.DataFrame({
        "transaction_id": ["T1", "T1", "T2"],
        "transaction_date": pd.to_datetime(["2026-10-01", "2026-10-01", "2026-10-02"]),
        "quantity_sold": [5, 5, 3],
    })
    result = dedupe_transactions(df)
    assert len(result) == 2


def test_clean_quantities_drops_negative_and_non_numeric():
    df = pd.DataFrame({
        "quantity_sold": [5, -3, "bad", None, 10],
    })
    clean, invalid_count = clean_quantities(df)
    assert invalid_count == 3
    assert list(clean["quantity_sold"]) == [5, 10]


def test_global_confirmed_dates_from_scope_sales():
    df = pd.DataFrame({"transaction_date": pd.to_datetime(["2026-10-01", "2026-10-03", "2026-10-03"])})
    dates = global_confirmed_dates(df)
    assert dates == {pd.Timestamp("2026-10-01"), pd.Timestamp("2026-10-03")}


def test_build_daily_series_zero_fills_only_confirmed_dates():
    # System confirmed operating Oct 1-5; this SKU only sold on Oct 1 and Oct 4.
    confirmed = {pd.Timestamp(d) for d in ["2026-10-01", "2026-10-02", "2026-10-03", "2026-10-04", "2026-10-05"]}
    sku_sales = pd.DataFrame({
        "transaction_date": pd.to_datetime(["2026-10-01", "2026-10-04"]),
        "quantity_sold": [10, 20],
    })
    series, unknown_days = build_daily_series(sku_sales, confirmed)
    assert unknown_days == 0
    assert series[pd.Timestamp("2026-10-02")] == 0.0  # confirmed-zero, not fabricated-unknown
    assert series[pd.Timestamp("2026-10-04")] == 20.0
    assert len(series) == 5


def test_build_daily_series_excludes_dates_outside_confirmed_coverage():
    # Overall system has a dark gap on Oct 3 (no confirmed activity anywhere);
    # that day must not silently become a zero for this sku.
    confirmed = {pd.Timestamp(d) for d in ["2026-10-01", "2026-10-02", "2026-10-04", "2026-10-05"]}
    series, unknown_days = build_daily_series(pd.DataFrame(columns=["transaction_date", "quantity_sold"]), confirmed)
    assert unknown_days == 1  # Oct 3 excluded, not assumed zero
    assert pd.Timestamp("2026-10-03") not in series.index


def test_weighted_moving_average_weights_recent_days_more():
    series = pd.Series([10.0, 10.0, 100.0], index=pd.date_range("2026-10-01", periods=3))
    value, points_used = weighted_moving_average(series, window_days=3)
    simple_avg = (10 + 10 + 100) / 3
    assert points_used == 3
    assert value > simple_avg  # the most recent (100) is weighted heaviest


def test_weighted_moving_average_empty_series_is_zero():
    assert weighted_moving_average(pd.Series(dtype=float), 7) == (0.0, 0)


def test_seasonal_naive_forecast_requires_minimum_weeks_per_weekday():
    short_series = pd.Series([5.0] * 10, index=pd.date_range("2026-10-01", periods=10))
    daily, reason = seasonal_naive_forecast(short_series, 7, pd.Timestamp("2026-10-11"), min_weeks=3)
    assert daily is None
    assert reason == "insufficient_weeks_per_weekday"


def test_seasonal_naive_forecast_uses_day_of_week_average():
    # 4 full weeks (28 days); Mondays are always 100, everything else 10.
    index = pd.date_range("2026-09-07", periods=28)  # 2026-09-07 is a Monday
    values = [100.0 if d.day_of_week == 0 else 10.0 for d in index]
    series = pd.Series(values, index=index)
    daily, reason = seasonal_naive_forecast(series, 7, index[-1] + pd.Timedelta(days=1), min_weeks=3)
    assert reason is None
    assert daily[0] == 100.0  # first forecast day is the next Monday


def test_forecast_core_insufficient_history():
    series = pd.Series([5.0, 5.0], index=pd.date_range("2026-10-01", periods=2))
    result = forecast_core(series, 0, 7, SETTINGS, pd.Timestamp("2026-10-03"))
    assert result["sufficient_data"] is False
    assert result["reason"] == "insufficient_history"
    assert result["forecast_daily"] is None


def test_forecast_core_sufficient_history_produces_flat_horizon():
    series = pd.Series([10.0] * 30, index=pd.date_range("2026-09-01", periods=30))
    result = forecast_core(series, 0, 7, SETTINGS, series.index.max() + pd.Timedelta(days=1))
    assert result["sufficient_data"] is True
    assert result["forecast_daily"] == [10.0] * 7
    assert result["forecast_total"] == 70.0
    assert result["historical_avg_daily_sales"] == 10.0


def test_forecast_core_warns_about_unknown_coverage_days():
    series = pd.Series([10.0] * 10, index=pd.date_range("2026-09-01", periods=10))
    result = forecast_core(series, 3, 7, SETTINGS, series.index.max() + pd.Timedelta(days=1))
    assert any("no confirmed sales activity" in w for w in result["warnings"])


def test_backtest_insufficient_history():
    series = pd.Series([5.0] * 5, index=pd.date_range("2026-10-01", periods=5))
    result = backtest(series, SETTINGS)
    assert result["evaluated"] is False
    assert result["reason"] == "insufficient_history_for_backtest"


def test_backtest_no_future_data_leakage():
    settings = DemandForecastSettings(moving_average_window_days=20, backtest_holdout_days=7, min_train_days_for_backtest=14)
    train = [10.0] * 20
    holdout = [100.0] * 7
    series = pd.Series(train + holdout, index=pd.date_range("2026-09-01", periods=27))

    result = backtest(series, settings)
    assert result["evaluated"] is True
    # If the holdout leaked into the averaging window, the prediction would
    # be pulled toward 100 and bias would not equal exactly 10 - 100 = -90.
    assert result["weighted_moving_average"]["bias"] == -90.0
    assert result["weighted_moving_average"]["mae"] == 90.0
    assert result["simple_average_baseline"]["bias"] == -90.0


def test_backtest_zero_actual_demand_in_holdout():
    series = pd.Series([5.0] * 14 + [0.0] * 7, index=pd.date_range("2026-09-01", periods=21))
    settings = DemandForecastSettings(moving_average_window_days=14, backtest_holdout_days=7, min_train_days_for_backtest=14)
    result = backtest(series, settings)
    assert result["evaluated"] is True
    assert result["zero_actual_demand_in_holdout"] is True
    assert result["weighted_moving_average"]["wape"] is None  # undefined, not fabricated
    assert result["weighted_moving_average"]["mae"] is not None  # still computable


def test_backtest_compares_against_simple_baseline_and_can_differ():
    # Strong upward trend: WMA (recency-weighted) should differ from the plain mean.
    train = list(range(1, 29))  # 1..28, increasing
    holdout = [28.0] * 7
    series = pd.Series(train + holdout, index=pd.date_range("2026-09-01", periods=35))
    settings = DemandForecastSettings(moving_average_window_days=28, backtest_holdout_days=7, min_train_days_for_backtest=14)
    result = backtest(series, settings)
    assert result["weighted_moving_average"]["mae"] != result["simple_average_baseline"]["mae"]


def test_detect_change_requires_minimum_windows():
    short_series = pd.Series([5.0] * 10, index=pd.date_range("2026-10-01", periods=10))
    assert detect_change(short_series, SETTINGS) is None


def test_detect_change_computes_percent_increase():
    baseline = [10.0] * 21
    recent = [20.0] * 7  # 100% increase
    series = pd.Series(baseline + recent, index=pd.date_range("2026-09-01", periods=28))
    change = detect_change(series, SETTINGS)
    assert change["percent_change"] == 100.0


def test_detect_change_zero_baseline_gives_no_percent_change():
    baseline = [0.0] * 21
    recent = [5.0] * 7
    series = pd.Series(baseline + recent, index=pd.date_range("2026-09-01", periods=28))
    change = detect_change(series, SETTINGS)
    assert change["percent_change"] is None  # can't compute a ratio from a zero base


# --------------------------------------------------------------------- #
# Section B: engine orchestration via fake services
# --------------------------------------------------------------------- #
PRODUCTS_COLUMNS = ["sku", "product_name", "category", "brand", "selling_price", "cost_price"]
STORES_COLUMNS = ["store_id", "store_name", "city", "region", "store_type"]
SALES_COLUMNS = ["transaction_id", "transaction_date", "store_id", "sku", "quantity_sold", "selling_price", "sales_channel"]
PROMOTIONS_COLUMNS = ["promotion_id", "sku", "promotion_name", "discount_percent", "start_date", "end_date", "promotion_channel"]


def _validate_sku(sku):
    if not isinstance(sku, str) or not sku.strip():
        raise ValueError(f"sku must be a non-empty string, got: {sku!r}")
    return sku.strip()


class FakeRetailDataService:
    """Minimal RetailDataService stand-in, built from in-memory DataFrames."""

    def __init__(self, products=None, stores=None, sales=None, promotions=None):
        self.products_df = products if products is not None else pd.DataFrame(columns=PRODUCTS_COLUMNS)
        self.stores_df = stores if stores is not None else pd.DataFrame(columns=STORES_COLUMNS)
        self.sales_df = sales if sales is not None else pd.DataFrame(columns=SALES_COLUMNS)
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

    def get_promotions(self, sku):
        sku = _validate_sku(sku)
        return self.promotions_df[self.promotions_df["sku"] == sku].reset_index(drop=True)


class FakeInventoryEngine:
    """Stand-in for InventoryRiskEngine, returning a canned
    get_product_inventory_analysis() result shaped like the real one."""

    def __init__(self, store_available=0.0, warehouse_available=0.0, warehouse_inbound=0.0,
                 suggested_replenishment_quantity=0, risk_level="unknown"):
        self.store_available = store_available
        self.warehouse_available = warehouse_available
        self.warehouse_inbound = warehouse_inbound
        self.suggested_replenishment_quantity = suggested_replenishment_quantity
        self.risk_level = risk_level

    def get_product_inventory_analysis(self, sku):
        return {
            "sku": sku,
            "observed": {
                "store_available_inventory": self.store_available,
                "warehouse": {
                    "warehouse_available": self.warehouse_available,
                    "warehouse_inbound": self.warehouse_inbound,
                },
            },
            "estimated": {"risk_level": self.risk_level},
            "recommendation": {"suggested_replenishment_quantity": self.suggested_replenishment_quantity},
        }


def _daily_sales_rows(sku, store_id, start_date, quantities):
    dates = pd.date_range(start_date, periods=len(quantities))
    return pd.DataFrame({
        "transaction_id": [f"TXN-{sku}-{i}" for i in range(len(quantities))],
        "transaction_date": dates,
        "store_id": store_id,
        "sku": sku,
        "quantity_sold": quantities,
        "selling_price": 10.0,
        "sales_channel": "in_store",
    })


def _basic_fixture(sku="SKU-TEST-0001", quantities=None, store_id="ST-001"):
    quantities = quantities if quantities is not None else [10.0] * 30
    products = pd.DataFrame([{
        "sku": sku, "product_name": "Test Widget", "category": "Home",
        "brand": "TestBrand", "selling_price": 10.0, "cost_price": 5.0,
    }])
    stores = pd.DataFrame([{
        "store_id": store_id, "store_name": "Test Store", "city": "Testville",
        "region": "Test", "store_type": "Flagship",
    }])
    sales = _daily_sales_rows(sku, store_id, "2026-09-01", quantities)
    service = FakeRetailDataService(products, stores, sales)
    return service, sku


def _engine(service, settings=None, inventory_engine=None):
    return DemandForecastEngine(
        service=service,
        settings=settings or SETTINGS,
        inventory_engine=inventory_engine or FakeInventoryEngine(),
    )


def test_forecast_with_valid_historical_data():
    service, sku = _basic_fixture(quantities=[10.0] * 30)
    engine = _engine(service)
    result = engine.forecast_demand(sku, horizon_days=7)
    assert result["sufficient_data"] is True
    assert result["horizon_days"] == 7
    assert len(result["forecast_daily"]) == 7
    assert result["total_forecast_demand"] == pytest.approx(70.0)
    assert result["forecast_method"] == "weighted_moving_average"


def test_forecast_insufficient_history():
    service, sku = _basic_fixture(quantities=[10.0] * 3)
    engine = _engine(service)
    result = engine.forecast_demand(sku)
    assert result["sufficient_data"] is False
    assert result["reason"] == "insufficient_history"
    assert result["total_forecast_demand"] is None


def test_forecast_unknown_but_well_formed_sku_is_graceful():
    # The system was confirmed operating (other SKUs sold) but this SKU
    # never did -- a confirmed zero-demand forecast, not a crash and not
    # "insufficient data" (the system's activity is real evidence of zero).
    service, _ = _basic_fixture()
    engine = _engine(service)
    result = engine.forecast_demand("SKU-NOT-REAL")
    assert result["product_found"] is False
    assert result["sufficient_data"] is True
    assert result["total_forecast_demand"] == 0.0


def test_forecast_missing_or_empty_sku_raises_value_error():
    engine = _engine(FakeRetailDataService())
    with pytest.raises(ValueError):
        engine.forecast_demand(None)
    with pytest.raises(ValueError):
        engine.forecast_demand("")


def test_forecast_horizon_validation():
    service, sku = _basic_fixture()
    engine = _engine(service)
    with pytest.raises(ValueError):
        engine.forecast_demand(sku, horizon_days=0)
    with pytest.raises(ValueError):
        engine.forecast_demand(sku, horizon_days=-3)
    with pytest.raises(ValueError):
        engine.forecast_demand(sku, horizon_days="7")


def test_forecast_handles_zero_sales_days():
    quantities = [10.0, 0.0, 0.0, 10.0] * 8  # genuine zero-sales days mixed in
    service, sku = _basic_fixture(quantities=quantities)
    engine = _engine(service)
    result = engine.forecast_demand(sku)
    assert result["sufficient_data"] is True
    assert result["historical_avg_daily_sales"] == pytest.approx(5.0)


def test_forecast_handles_negative_and_invalid_quantities():
    sku = "SKU-TEST-0002"
    store_id = "ST-001"
    products = pd.DataFrame([{
        "sku": sku, "product_name": "Bad Data Widget", "category": "Home",
        "brand": "TestBrand", "selling_price": 10.0, "cost_price": 5.0,
    }])
    stores = pd.DataFrame([{"store_id": store_id, "store_name": "Test Store", "city": "X", "region": "Y", "store_type": "Flagship"}])
    good = _daily_sales_rows(sku, store_id, "2026-09-01", [10.0] * 20)
    bad = pd.DataFrame({
        "transaction_id": ["BAD-1", "BAD-2"],
        "transaction_date": pd.to_datetime(["2026-09-21", "2026-09-22"]),
        "store_id": store_id, "sku": sku,
        "quantity_sold": [-5, "oops"],
        "selling_price": 10.0, "sales_channel": "in_store",
    })
    sales = pd.concat([good, bad], ignore_index=True)
    service = FakeRetailDataService(products, stores, sales)
    engine = _engine(service)
    result = engine.forecast_demand(sku)
    assert result["sufficient_data"] is True
    assert any("invalid" in w for w in result["data_quality_warnings"])


def test_store_level_forecasting_scopes_to_one_store():
    sku = "SKU-TEST-0003"
    products = pd.DataFrame([{
        "sku": sku, "product_name": "Multi Store Widget", "category": "Home",
        "brand": "TestBrand", "selling_price": 10.0, "cost_price": 5.0,
    }])
    stores = pd.DataFrame([
        {"store_id": "ST-001", "store_name": "A", "city": "X", "region": "Y", "store_type": "Flagship"},
        {"store_id": "ST-002", "store_name": "B", "city": "X", "region": "Y", "store_type": "Flagship"},
    ])
    sales_a = _daily_sales_rows(sku, "ST-001", "2026-09-01", [10.0] * 30)
    sales_b = _daily_sales_rows(sku, "ST-002", "2026-09-01", [2.0] * 30)
    service = FakeRetailDataService(products, stores, pd.concat([sales_a, sales_b], ignore_index=True))
    engine = _engine(service)

    result_a = engine.forecast_demand(sku, store_id="ST-001")
    result_b = engine.forecast_demand(sku, store_id="ST-002")
    assert result_a["historical_avg_daily_sales"] == pytest.approx(10.0)
    assert result_b["historical_avg_daily_sales"] == pytest.approx(2.0)
    assert result_a["store_name"] == "A"


def test_store_level_forecast_unknown_store_raises():
    service, sku = _basic_fixture()
    engine = _engine(service)
    with pytest.raises(ValueError):
        engine.forecast_demand(sku, store_id="ST-999")


def test_detect_demand_spikes_flags_sku_with_increase():
    quantities = [5.0] * 21 + [20.0] * 7  # 300% increase in the recent window
    service, sku = _basic_fixture(quantities=quantities)
    engine = _engine(service)
    spikes = engine.detect_demand_spikes()
    assert len(spikes) == 1
    assert spikes[0]["sku"] == sku
    assert spikes[0]["percent_change"] > 0


def test_detect_declining_demand_flags_sku_with_decrease():
    quantities = [20.0] * 21 + [5.0] * 7  # 75% decrease
    service, sku = _basic_fixture(quantities=quantities)
    engine = _engine(service)
    declines = engine.detect_declining_demand()
    assert len(declines) == 1
    assert declines[0]["sku"] == sku
    assert declines[0]["percent_change"] < 0


def test_detect_demand_spikes_notes_promotion_overlap_without_claiming_causation():
    quantities = [5.0] * 21 + [20.0] * 7
    sku = "SKU-TEST-0001"
    store_id = "ST-001"
    products = pd.DataFrame([{
        "sku": sku, "product_name": "Test Widget", "category": "Home",
        "brand": "TestBrand", "selling_price": 10.0, "cost_price": 5.0,
    }])
    stores = pd.DataFrame([{"store_id": store_id, "store_name": "Test Store", "city": "X", "region": "Y", "store_type": "Flagship"}])
    sales = _daily_sales_rows(sku, store_id, "2026-09-01", quantities)
    recent_start = sales["transaction_date"].iloc[-7]
    promotions = pd.DataFrame([{
        "promotion_id": "PROMO-0001", "sku": sku, "promotion_name": "Test Promo",
        "discount_percent": 20, "start_date": recent_start, "end_date": sales["transaction_date"].iloc[-1],
        "promotion_channel": "all_channels",
    }])
    service = FakeRetailDataService(products, stores, sales, promotions)
    engine = _engine(service)
    spikes = engine.detect_demand_spikes()
    assert spikes[0]["promotion_overlap"] is True
    assert "may or may not explain" in spikes[0]["note"]


def test_compare_forecast_with_inventory_reuses_inventory_agent():
    service, sku = _basic_fixture(quantities=[10.0] * 30)
    inventory_engine = FakeInventoryEngine(
        store_available=20.0, warehouse_available=500.0, warehouse_inbound=50.0,
        suggested_replenishment_quantity=30, risk_level="medium",
    )
    engine = _engine(service, inventory_engine=inventory_engine)
    result = engine.compare_forecast_with_inventory(sku, horizon_days=7)

    assert result["current_available_inventory"] == 20.0
    assert result["known_inbound_stock"] == 50.0
    assert result["forecast_total_demand"] == pytest.approx(70.0)
    assert result["estimated_demand_gap_vs_store_available"] == pytest.approx(50.0)  # 70 - 20
    assert result["estimated_demand_gap_vs_available_plus_inbound"] == pytest.approx(0.0)  # 70 - (20 + 50)
    assert result["inventory_agent_suggested_replenishment_quantity"] == 30
    assert result["recommend_investigating_replenishment"] is True
    assert "not a final replenishment quantity" in result["disclaimer"]


def test_compare_forecast_with_inventory_handles_missing_inbound_data():
    service, sku = _basic_fixture(quantities=[10.0] * 30)
    inventory_engine = FakeInventoryEngine(store_available=100.0, warehouse_available=0.0, warehouse_inbound=0.0)
    engine = _engine(service, inventory_engine=inventory_engine)
    result = engine.compare_forecast_with_inventory(sku, horizon_days=7)

    assert result["known_inbound_stock"] == 0.0
    # with zero inbound, both gap figures should agree
    assert result["estimated_demand_gap_vs_store_available"] == result["estimated_demand_gap_vs_available_plus_inbound"]


def test_compare_forecast_with_inventory_insufficient_forecast_data():
    service, sku = _basic_fixture(quantities=[10.0] * 3)  # too little history
    engine = _engine(service)
    result = engine.compare_forecast_with_inventory(sku)
    assert result["forecast_total_demand"] is None
    assert result["recommend_investigating_replenishment"] is False
    assert any("insufficient history" in w for w in result["data_limitations"])


def test_evaluate_forecast_zero_actual_demand():
    quantities = [10.0] * 14 + [0.0] * 7
    service, sku = _basic_fixture(quantities=quantities)
    settings = DemandForecastSettings(moving_average_window_days=14, backtest_holdout_days=7, min_train_days_for_backtest=14)
    engine = _engine(service, settings=settings)
    result = engine.evaluate_forecast(sku)
    assert result["backtest"]["evaluated"] is True
    assert result["backtest"]["zero_actual_demand_in_holdout"] is True
    assert result["backtest"]["weighted_moving_average"]["wape"] is None


def test_get_top_forecasted_products_sorted_descending():
    sku_a = "SKU-TEST-000A"
    sku_b = "SKU-TEST-000B"
    products = pd.DataFrame([
        {"sku": sku_a, "product_name": "A", "category": "Home", "brand": "X", "selling_price": 10.0, "cost_price": 5.0},
        {"sku": sku_b, "product_name": "B", "category": "Home", "brand": "X", "selling_price": 10.0, "cost_price": 5.0},
    ])
    stores = pd.DataFrame([{"store_id": "ST-001", "store_name": "A", "city": "X", "region": "Y", "store_type": "Flagship"}])
    sales = pd.concat([
        _daily_sales_rows(sku_a, "ST-001", "2026-09-01", [5.0] * 30),
        _daily_sales_rows(sku_b, "ST-001", "2026-09-01", [50.0] * 30),
    ], ignore_index=True)
    service = FakeRetailDataService(products, stores, sales)
    engine = _engine(service)
    top = engine.get_top_forecasted_products(limit=2)
    assert top[0]["sku"] == sku_b
    assert top[0]["total_forecast_demand"] > top[1]["total_forecast_demand"]


def test_get_top_forecasted_products_limit_validation():
    engine = _engine(FakeRetailDataService())
    with pytest.raises(ValueError):
        engine.get_top_forecasted_products(limit=0)


def test_get_demand_summary_for_single_sku():
    service, sku = _basic_fixture(quantities=[10.0] * 30)
    engine = _engine(service)
    summary = engine.get_demand_summary(sku=sku)
    assert summary["sku"] == sku
    assert summary["total_forecast_demand_next_horizon"] == pytest.approx(70.0)


def test_get_demand_summary_catalog_wide_empty_dataset_does_not_crash():
    engine = _engine(FakeRetailDataService())
    summary = engine.get_demand_summary()
    assert summary["total_products"] == 0
    assert summary["total_forecast_demand_next_horizon"] == 0.0


# --------------------------------------------------------------------- #
# Section C: smoke test against the real project data
# --------------------------------------------------------------------- #
def test_default_engine_runs_end_to_end_against_real_data():
    summary = get_demand_summary()
    assert summary["total_products"] > 0
