"""
Tests for inventory_agent/risk_engine.py.

Section A tests the pure, side-effect-free business-rule functions directly
with constructed inputs -- no data layer, no I/O, exact boundary checks.

Section B tests InventoryRiskEngine's orchestration using a lightweight
FakeRetailDataService (mirrors RetailDataService's method surface and
sku-validation behavior) so edge cases -- empty datasets, unknown SKUs,
negative/missing data, insufficient warehouse stock -- can be constructed
precisely without touching the real CSVs.

Section C is a light end-to-end smoke test against the real project data,
confirming the engine's default (production) wiring still works.
"""

import pandas as pd
import pytest

from inventory_agent.config import (
    InventoryRiskSettings,
    RISK_CRITICAL,
    RISK_HIGH,
    RISK_LOW,
    RISK_MEDIUM,
    RISK_UNKNOWN,
)
from inventory_agent.risk_engine import (
    InventoryRiskEngine,
    avg_daily_sales,
    classify_risk,
    clip_non_negative_sum,
    days_of_inventory,
    get_inventory_summary,
    is_excess_inventory,
    suggested_replenishment,
)

SETTINGS = InventoryRiskSettings()  # defaults: high<2, medium<5, target=14 days


# --------------------------------------------------------------------- #
# Section A: pure business-rule functions
# --------------------------------------------------------------------- #
def test_days_of_inventory_correct_calculation():
    assert days_of_inventory(20, 4) == 5.0
    assert days_of_inventory(7, 3.5) == 2.0


def test_days_of_inventory_zero_average_daily_sales_is_unavailable():
    assert days_of_inventory(100, 0) is None
    assert days_of_inventory(100, None) is None


def test_days_of_inventory_negative_sales_velocity_is_unavailable():
    assert days_of_inventory(100, -5) is None


def test_classify_risk_zero_average_daily_sales_is_unknown():
    assert classify_risk(available_inventory=50, sales_velocity=0, days_remaining=None, settings=SETTINGS) == RISK_UNKNOWN


def test_classify_risk_zero_inventory_positive_sales_is_critical():
    days = days_of_inventory(0, 3)
    assert classify_risk(available_inventory=0, sales_velocity=3, days_remaining=days, settings=SETTINGS) == RISK_CRITICAL


def test_classify_risk_high_boundary():
    # just under the high-risk threshold (2 days) -> high
    days = days_of_inventory(19, 10)  # 1.9 days
    assert classify_risk(19, 10, days, SETTINGS) == RISK_HIGH


def test_classify_risk_medium_boundary_inclusive_at_two_days():
    days = days_of_inventory(20, 10)  # exactly 2.0 days -> medium, not high
    assert classify_risk(20, 10, days, SETTINGS) == RISK_MEDIUM


def test_classify_risk_medium_just_under_five_days():
    days = days_of_inventory(49, 10)  # 4.9 days -> medium
    assert classify_risk(49, 10, days, SETTINGS) == RISK_MEDIUM


def test_classify_risk_low_boundary_inclusive_at_five_days():
    days = days_of_inventory(50, 10)  # exactly 5.0 days -> low, not medium
    assert classify_risk(50, 10, days, SETTINGS) == RISK_LOW


def test_classify_risk_low_well_stocked():
    days = days_of_inventory(1000, 10)
    assert classify_risk(1000, 10, days, SETTINGS) == RISK_LOW


def test_suggested_replenishment_no_sales_velocity_suggests_nothing():
    qty, basis, capped = suggested_replenishment(available_inventory=10, sales_velocity=0, warehouse_available=500, settings=SETTINGS)
    assert qty == 0
    assert basis == "no_recent_sales_velocity"
    assert capped is False


def test_suggested_replenishment_is_capped_by_warehouse_availability():
    # target = 10/day * 14 days = 140 units needed, minus 5 available = 135 raw
    qty, basis, capped = suggested_replenishment(
        available_inventory=5, sales_velocity=10, warehouse_available=20, settings=SETTINGS
    )
    assert qty == 20
    assert capped is True
    assert basis == "target_days_of_coverage"


def test_suggested_replenishment_never_exceeds_warehouse_even_with_ample_demand():
    qty, _, capped = suggested_replenishment(
        available_inventory=0, sales_velocity=1000, warehouse_available=7, settings=SETTINGS
    )
    assert qty <= 7
    assert capped is True


def test_suggested_replenishment_within_warehouse_capacity_not_capped():
    qty, _, capped = suggested_replenishment(
        available_inventory=0, sales_velocity=1, warehouse_available=500, settings=SETTINGS
    )
    assert qty == 14  # 1/day * 14 days target, well under warehouse_available
    assert capped is False


def test_suggested_replenishment_handles_negative_and_missing_inputs():
    qty, _, _ = suggested_replenishment(available_inventory=-5, sales_velocity=10, warehouse_available=-20, settings=SETTINGS)
    assert qty == 0  # negative warehouse_available clamped to 0


def test_clip_non_negative_sum_handles_negative_and_missing_values():
    series = pd.Series([10, -5, None, 3])
    assert clip_non_negative_sum(series) == 13.0


def test_clip_non_negative_sum_empty_series_is_zero():
    assert clip_non_negative_sum(pd.Series([], dtype=float)) == 0.0
    assert clip_non_negative_sum(None) == 0.0


def test_avg_daily_sales_correct_window_calculation():
    reference_date = pd.Timestamp("2026-10-27")
    sales = pd.DataFrame({
        "transaction_date": pd.to_datetime([
            "2026-10-27", "2026-10-25", "2026-10-20", "2026-09-01",
        ]),
        "quantity_sold": [5, 5, 100, 999],
    })
    # last 7 days (> Oct 20): Oct 27 (5) + Oct 25 (5) = 10 units / 7 days
    assert avg_daily_sales(sales, reference_date, 7) == pytest.approx(10 / 7)


def test_avg_daily_sales_empty_or_missing_inputs_is_zero():
    assert avg_daily_sales(pd.DataFrame(), pd.Timestamp("2026-10-27"), 7) == 0.0
    assert avg_daily_sales(None, pd.Timestamp("2026-10-27"), 7) == 0.0
    assert avg_daily_sales(pd.DataFrame({"transaction_date": [], "quantity_sold": []}), None, 7) == 0.0


def test_is_excess_inventory_with_sales_velocity():
    assert is_excess_inventory(available_inventory=1000, sales_velocity=1, days_remaining=1000, settings=SETTINGS) is True
    assert is_excess_inventory(available_inventory=10, sales_velocity=5, days_remaining=2, settings=SETTINGS) is False


def test_is_excess_inventory_with_zero_sales_velocity():
    assert is_excess_inventory(available_inventory=1000, sales_velocity=0, days_remaining=None, settings=SETTINGS) is True
    assert is_excess_inventory(available_inventory=10, sales_velocity=0, days_remaining=None, settings=SETTINGS) is False


# --------------------------------------------------------------------- #
# Section B: engine orchestration via a fake data service
# --------------------------------------------------------------------- #
PRODUCTS_COLUMNS = ["sku", "product_name", "category", "brand", "selling_price", "cost_price"]
STORES_COLUMNS = ["store_id", "store_name", "city", "region", "store_type"]
SALES_COLUMNS = ["transaction_id", "transaction_date", "store_id", "sku", "quantity_sold", "selling_price", "sales_channel"]
INVENTORY_COLUMNS = ["sku", "location_id", "location_type", "on_hand_quantity", "reserved_quantity", "available_quantity", "last_updated"]
ORDERS_COLUMNS = ["order_id", "customer_id", "order_date", "sku", "quantity", "order_status", "fulfillment_location", "promised_delivery_date"]
WAREHOUSE_COLUMNS = ["warehouse_id", "sku", "on_hand_quantity", "reserved_quantity", "inbound_quantity", "supplier_lead_time_days"]


def _validate_sku(sku):
    if not isinstance(sku, str) or not sku.strip():
        raise ValueError(f"sku must be a non-empty string, got: {sku!r}")
    return sku.strip()


class FakeRetailDataService:
    """Minimal stand-in for RetailDataService, built from in-memory
    DataFrames instead of CSV files, with the same sku-validation
    convention (ValueError on empty/None, empty result on unknown-but-valid)."""

    def __init__(self, products=None, stores=None, sales=None, inventory=None, orders=None, warehouse=None):
        self.products_df = products if products is not None else pd.DataFrame(columns=PRODUCTS_COLUMNS)
        self.stores_df = stores if stores is not None else pd.DataFrame(columns=STORES_COLUMNS)
        self.sales_df = sales if sales is not None else pd.DataFrame(columns=SALES_COLUMNS)
        self.inventory_df = inventory if inventory is not None else pd.DataFrame(columns=INVENTORY_COLUMNS)
        self.orders_df = orders if orders is not None else pd.DataFrame(columns=ORDERS_COLUMNS)
        self.warehouse_df = warehouse if warehouse is not None else pd.DataFrame(columns=WAREHOUSE_COLUMNS)

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


def _one_sku_fixture(available_quantity, sales_rows, warehouse_available=100, sku="SKU-TEST-0001"):
    products = pd.DataFrame([{
        "sku": sku, "product_name": "Test Widget", "category": "Home",
        "brand": "TestBrand", "selling_price": 10.0, "cost_price": 5.0,
    }])
    stores = pd.DataFrame([{
        "store_id": "ST-001", "store_name": "Test Store", "city": "Testville",
        "region": "Test", "store_type": "Flagship",
    }])
    inventory = pd.DataFrame([{
        "sku": sku, "location_id": "ST-001", "location_type": "store",
        "on_hand_quantity": available_quantity, "reserved_quantity": 0,
        "available_quantity": available_quantity, "last_updated": "2026-10-27",
    }])
    sales = pd.DataFrame([
        {
            "transaction_id": f"TXN-{i}", "transaction_date": pd.Timestamp(date),
            "store_id": "ST-001", "sku": sku, "quantity_sold": qty,
            "selling_price": 10.0, "sales_channel": "in_store",
        }
        for i, (date, qty) in enumerate(sales_rows)
    ], columns=SALES_COLUMNS) if sales_rows else pd.DataFrame(columns=SALES_COLUMNS)
    orders = pd.DataFrame(columns=ORDERS_COLUMNS)
    warehouse = pd.DataFrame([{
        "warehouse_id": "WH-01", "sku": sku, "on_hand_quantity": warehouse_available,
        "reserved_quantity": 0, "inbound_quantity": 0, "supplier_lead_time_days": 7,
    }])
    return FakeRetailDataService(products, stores, sales, inventory, orders, warehouse), sku


def test_zero_inventory_with_positive_sales_is_critical():
    service, sku = _one_sku_fixture(
        available_quantity=0,
        sales_rows=[("2026-10-27", 5), ("2026-10-26", 5)],
    )
    engine = InventoryRiskEngine(service=service, settings=SETTINGS)
    result = engine.get_product_inventory_analysis(sku)
    assert result["estimated"]["risk_level"] == RISK_CRITICAL
    assert result["observed"]["store_available_inventory"] == 0


def test_zero_average_daily_sales_marks_days_of_inventory_unavailable():
    service, sku = _one_sku_fixture(available_quantity=50, sales_rows=[])
    engine = InventoryRiskEngine(service=service, settings=SETTINGS)
    result = engine.get_product_inventory_analysis(sku)
    assert result["estimated"]["days_of_inventory"] is None
    assert result["estimated"]["risk_level"] == RISK_UNKNOWN
    assert result["estimated"]["days_of_inventory_unavailable_reason"] == "zero_average_daily_sales"


def test_unknown_but_well_formed_sku_returns_graceful_not_found_result():
    service, _ = _one_sku_fixture(available_quantity=10, sales_rows=[("2026-10-27", 1)])
    engine = InventoryRiskEngine(service=service, settings=SETTINGS)
    result = engine.get_product_inventory_analysis("SKU-NOT-REAL")
    assert result["product_found"] is False
    assert result["product"] is None
    assert result["observed"]["store_available_inventory"] == 0
    assert result["estimated"]["risk_level"] == RISK_UNKNOWN  # no sales data for this sku either


def test_missing_sku_input_raises_value_error():
    engine = InventoryRiskEngine(service=FakeRetailDataService(), settings=SETTINGS)
    with pytest.raises(ValueError):
        engine.get_product_inventory_analysis(None)
    with pytest.raises(ValueError):
        engine.get_product_inventory_analysis("")
    with pytest.raises(ValueError):
        engine.get_warehouse_availability(None)


def test_insufficient_warehouse_stock_caps_replenishment_quantity():
    service, sku = _one_sku_fixture(
        available_quantity=0,
        sales_rows=[("2026-10-27", 20), ("2026-10-26", 20)],
        warehouse_available=3,
    )
    engine = InventoryRiskEngine(service=service, settings=SETTINGS)
    result = engine.get_product_inventory_analysis(sku)
    assert result["recommendation"]["suggested_replenishment_quantity"] <= 3
    assert result["recommendation"]["capped_by_warehouse_availability"] is True


def test_negative_and_missing_inventory_data_does_not_crash():
    sku = "SKU-TEST-0002"
    products = pd.DataFrame([{
        "sku": sku, "product_name": "Bad Data Widget", "category": "Home",
        "brand": "TestBrand", "selling_price": 10.0, "cost_price": 5.0,
    }])
    stores = pd.DataFrame([
        {"store_id": "ST-001", "store_name": "A", "city": "X", "region": "Y", "store_type": "Flagship"},
        {"store_id": "ST-002", "store_name": "B", "city": "X", "region": "Y", "store_type": "Flagship"},
    ])
    inventory = pd.DataFrame([
        {"sku": sku, "location_id": "ST-001", "location_type": "store",
         "on_hand_quantity": -5, "reserved_quantity": 0, "available_quantity": -5, "last_updated": "2026-10-27"},
        {"sku": sku, "location_id": "ST-002", "location_type": "store",
         "on_hand_quantity": None, "reserved_quantity": None, "available_quantity": None, "last_updated": "2026-10-27"},
    ])
    sales = pd.DataFrame(columns=SALES_COLUMNS)
    orders = pd.DataFrame(columns=ORDERS_COLUMNS)
    warehouse = pd.DataFrame(columns=WAREHOUSE_COLUMNS)
    service = FakeRetailDataService(products, stores, sales, inventory, orders, warehouse)

    engine = InventoryRiskEngine(service=service, settings=SETTINGS)
    result = engine.get_product_inventory_analysis(sku)  # must not raise
    assert result["observed"]["store_available_inventory"] == 0  # negative/missing clamped to 0


def test_empty_datasets_do_not_crash_any_public_function():
    engine = InventoryRiskEngine(service=FakeRetailDataService(), settings=SETTINGS)

    assert engine.get_inventory_risks() == []
    assert engine.get_store_inventory_risks() == []
    assert engine.get_top_stockout_risks(limit=5) == []
    assert engine.get_replenishment_recommendations() == []

    summary = engine.get_inventory_summary()
    assert summary["total_products"] == 0
    assert all(count == 0 for count in summary["risk_level_counts"].values())

    # a well-formed sku against an empty catalog: graceful "not found", not an error
    analysis = engine.get_product_inventory_analysis("SKU-ANY-0001")
    assert analysis["product_found"] is False

    availability = engine.get_warehouse_availability("SKU-ANY-0001")
    assert availability["warehouse_available"] == 0.0


def test_get_store_inventory_risks_unknown_store_id_raises_value_error():
    service, _ = _one_sku_fixture(available_quantity=10, sales_rows=[])
    engine = InventoryRiskEngine(service=service, settings=SETTINGS)
    with pytest.raises(ValueError):
        engine.get_store_inventory_risks(store_id="ST-999")


def test_get_store_inventory_risks_flags_shortage_for_known_store():
    service, sku = _one_sku_fixture(
        available_quantity=0,
        sales_rows=[("2026-10-27", 5), ("2026-10-26", 5)],
    )
    engine = InventoryRiskEngine(service=service, settings=SETTINGS)
    results = engine.get_store_inventory_risks(store_id="ST-001")
    assert len(results) == 1
    assert results[0]["sku"] == sku
    assert results[0]["estimated"]["risk_level"] == RISK_CRITICAL


def test_top_stockout_risks_excludes_unknown_and_respects_limit():
    service, sku = _one_sku_fixture(
        available_quantity=0,
        sales_rows=[("2026-10-27", 5)],
    )
    engine = InventoryRiskEngine(service=service, settings=SETTINGS)
    results = engine.get_top_stockout_risks(limit=1)
    assert len(results) == 1
    assert results[0]["sku"] == sku

    with pytest.raises(ValueError):
        engine.get_top_stockout_risks(limit=0)


def test_replenishment_recommendations_only_includes_positive_suggestions():
    service, sku = _one_sku_fixture(
        available_quantity=0,
        sales_rows=[("2026-10-27", 10), ("2026-10-26", 10)],
        warehouse_available=200,
    )
    engine = InventoryRiskEngine(service=service, settings=SETTINGS)
    results = engine.get_replenishment_recommendations()
    assert len(results) == 1
    assert results[0]["sku"] == sku
    assert results[0]["recommendation"]["suggested_replenishment_quantity"] > 0


# --------------------------------------------------------------------- #
# Section C: smoke test against the real project data
# --------------------------------------------------------------------- #
def test_default_engine_runs_end_to_end_against_real_data():
    summary = get_inventory_summary()
    assert summary["total_products"] > 0
    assert sum(summary["risk_level_counts"].values()) == summary["total_products"]
