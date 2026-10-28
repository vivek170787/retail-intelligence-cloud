"""
Tests for dashboard/data_prep.py.

This module has no Streamlit dependency, so it's tested as plain Python
against a FakeRetailDataService wired through the real
RetailOrchestrationService/RetailIntelligenceOrchestrator -- genuine
integration coverage of the actual agents, same pattern used throughout
this project's other test suites.
"""

import pandas as pd
import pytest

from orchestration.service import RetailOrchestrationService
from orchestration.query_orchestrator import RetailIntelligenceOrchestrator
from dashboard import data_prep

PRODUCTS_COLUMNS = ["sku", "product_name", "category", "brand", "selling_price", "cost_price"]
STORES_COLUMNS = ["store_id", "store_name", "city", "region", "store_type"]
SALES_COLUMNS = ["transaction_id", "transaction_date", "store_id", "sku", "quantity_sold", "selling_price", "sales_channel"]
INVENTORY_COLUMNS = ["sku", "location_id", "location_type", "on_hand_quantity", "reserved_quantity", "available_quantity", "last_updated"]
ORDERS_COLUMNS = ["order_id", "customer_id", "order_date", "sku", "quantity", "order_status", "fulfillment_location", "promised_delivery_date"]
WAREHOUSE_COLUMNS = ["warehouse_id", "sku", "on_hand_quantity", "reserved_quantity", "inbound_quantity", "supplier_lead_time_days"]
PROMOTIONS_COLUMNS = ["promotion_id", "sku", "promotion_name", "discount_percent", "start_date", "end_date", "promotion_channel"]
MARKETPLACE_COLUMNS = ["marketplace", "listing_id", "sku", "listing_status", "listed_price", "available_quantity"]


def _validate_sku(sku):
    if not isinstance(sku, str) or not sku.strip():
        raise ValueError(f"sku must be a non-empty string, got: {sku!r}")
    return sku.strip()


class FakeRetailDataService:
    def __init__(self, products=None, stores=None, sales=None, inventory=None,
                 orders=None, warehouse=None, promotions=None, marketplace=None):
        self.products_df = products if products is not None else pd.DataFrame(columns=PRODUCTS_COLUMNS)
        self.stores_df = stores if stores is not None else pd.DataFrame(columns=STORES_COLUMNS)
        self.sales_df = sales if sales is not None else pd.DataFrame(columns=SALES_COLUMNS)
        self.inventory_df = inventory if inventory is not None else pd.DataFrame(columns=INVENTORY_COLUMNS)
        self.orders_df = orders if orders is not None else pd.DataFrame(columns=ORDERS_COLUMNS)
        self.warehouse_df = warehouse if warehouse is not None else pd.DataFrame(columns=WAREHOUSE_COLUMNS)
        self.promotions_df = promotions if promotions is not None else pd.DataFrame(columns=PROMOTIONS_COLUMNS)
        self.marketplace_df = marketplace if marketplace is not None else pd.DataFrame(columns=MARKETPLACE_COLUMNS)

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

    def get_orders(self):
        return self.orders_df

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

    def get_marketplace_listings(self, sku):
        sku = _validate_sku(sku)
        return self.marketplace_df[self.marketplace_df["sku"] == sku].reset_index(drop=True)


def _daily_sales_rows(sku, store_id, start_date, quantities):
    dates = pd.date_range(start_date, periods=len(quantities))
    return pd.DataFrame({
        "transaction_id": [f"TXN-{sku}-{i}" for i in range(len(quantities))],
        "transaction_date": dates, "store_id": store_id, "sku": sku,
        "quantity_sold": quantities, "selling_price": 10.0, "sales_channel": "in_store",
    })


def _order_row(order_id, sku, quantity, status, fulfillment_location, promised_delivery_date, order_date="2026-10-01", customer_id="CUST-00001"):
    return {
        "order_id": order_id, "customer_id": customer_id,
        "order_date": pd.Timestamp(order_date), "sku": sku, "quantity": quantity,
        "order_status": status, "fulfillment_location": fulfillment_location,
        "promised_delivery_date": pd.Timestamp(promised_delivery_date) if promised_delivery_date else pd.NaT,
    }


def _build_fixture(sku="SKU-ABC-0001", store_id="ST-001", store_available=10.0,
                    sales_quantities=None, orders=None, promotions=None):
    products = pd.DataFrame([{
        "sku": sku, "product_name": "Test Widget", "category": "Home",
        "brand": "TestBrand", "selling_price": 10.0, "cost_price": 5.0,
    }])
    stores = pd.DataFrame([{
        "store_id": store_id, "store_name": "Test Store", "city": "Testville",
        "region": "Test", "store_type": "Flagship",
    }])
    inventory = pd.DataFrame([{
        "sku": sku, "location_id": store_id, "location_type": "store",
        "on_hand_quantity": store_available, "reserved_quantity": 0,
        "available_quantity": store_available, "last_updated": "2026-10-27",
    }])
    warehouse = pd.DataFrame([{
        "warehouse_id": "WH-01", "sku": sku,
        "on_hand_quantity": 100.0, "reserved_quantity": 0.0,
        "inbound_quantity": 0.0, "supplier_lead_time_days": 5,
    }])
    sales = _daily_sales_rows(sku, store_id, "2026-08-01", sales_quantities or [10.0] * 60)
    orders_df = pd.DataFrame(orders) if orders else pd.DataFrame(columns=ORDERS_COLUMNS)
    promos_df = pd.DataFrame(promotions) if promotions else pd.DataFrame(columns=PROMOTIONS_COLUMNS)
    service = FakeRetailDataService(products, stores, sales, inventory, orders_df, warehouse, promos_df)
    return service, sku, store_id


def _orchestrator(service):
    return RetailIntelligenceOrchestrator(orchestration_service=RetailOrchestrationService(service=service))


# --------------------------------------------------------------------- #
# Command Center
# --------------------------------------------------------------------- #
def test_build_command_center_shape():
    service, sku, _ = _build_fixture(store_available=0.0, sales_quantities=[10.0] * 60)
    orch = _orchestrator(service)
    data = data_prep.build_command_center(orch)
    assert "severity" in data
    assert data["inventory_summary"] is not None
    assert data["fulfillment_summary"] is not None
    assert isinstance(data["data_gaps"], list)


def test_build_command_center_labels_unavailable_metrics_on_agent_failure():
    service, sku, _ = _build_fixture()
    svc = RetailOrchestrationService(service=service)

    class FailingInventoryEngine:
        def get_inventory_summary(self):
            raise RuntimeError("down")
        def get_top_stockout_risks(self, limit=10):
            raise RuntimeError("down")
        def get_product_inventory_analysis(self, sku):
            raise RuntimeError("down")
        def get_replenishment_recommendations(self):
            raise RuntimeError("down")
        def get_inventory_risks(self):
            raise RuntimeError("down")

    svc2 = RetailOrchestrationService(service=service, inventory_engine=FailingInventoryEngine())
    orch = RetailIntelligenceOrchestrator(orchestration_service=svc2)
    data = data_prep.build_command_center(orch)
    assert data["inventory_summary"] is None  # explicitly None, never a fabricated number
    assert any("inventory" in g.lower() for g in data["data_gaps"])


# --------------------------------------------------------------------- #
# Inventory & Demand
# --------------------------------------------------------------------- #
def test_build_inventory_table_shape_and_columns():
    service, sku, _ = _build_fixture(store_available=0.0, sales_quantities=[10.0] * 60)
    orch = _orchestrator(service)
    df, error = data_prep.build_inventory_table(orch)
    assert error is None
    assert sku in df["sku"].values
    assert {"risk_level", "days_of_inventory", "suggested_replenishment_qty"}.issubset(df.columns)


def test_build_store_breakdown():
    service, sku, store_id = _build_fixture(store_available=42.0)
    orch = _orchestrator(service)
    df, analysis, error = data_prep.build_store_breakdown(orch, sku)
    assert error is None
    assert df.iloc[0]["available_quantity"] == 42.0
    assert analysis["sku"] == sku


def test_build_sales_history_series_confirmed_coverage():
    service, sku, _ = _build_fixture(sales_quantities=[7.0] * 30)
    orch = _orchestrator(service)
    series, error = data_prep.build_sales_history_series(orch, sku)
    assert error is None
    assert len(series) == 30
    assert series.iloc[0] == 7.0


def test_build_catalog_sales_history_series_aggregates_all_skus():
    service, sku, _ = _build_fixture(sales_quantities=[7.0] * 30)
    orch = _orchestrator(service)

    # Add a second SKU's sales on the same dates so the catalog-wide series
    # must reflect both products combined, not just the fixture's primary SKU.
    extra_rows = service.sales_df.copy()
    extra_rows["sku"] = "SKU-EXTRA-0001"
    extra_rows["transaction_id"] = extra_rows["transaction_id"] + "-extra"
    service.sales_df = pd.concat([service.sales_df, extra_rows], ignore_index=True)

    series, error = data_prep.build_catalog_sales_history_series(orch)
    assert error is None
    assert len(series) == 30
    assert series.iloc[0] == 14.0  # 7.0 from each of the two SKUs on the same day


def test_build_demand_forecast():
    service, sku, _ = _build_fixture(sales_quantities=[5.0] * 60)
    orch = _orchestrator(service)
    forecast, error = data_prep.build_demand_forecast(orch, sku, horizon_days=7)
    assert error is None
    assert forecast["sufficient_data"] is True
    assert len(forecast["forecast_daily"]) == 7


def test_build_replenishment_table_empty_state():
    service, sku, _ = _build_fixture(store_available=1000.0, sales_quantities=[1.0] * 60)
    orch = _orchestrator(service)
    df, error = data_prep.build_replenishment_table(orch)
    assert error is None
    assert df.empty  # well-stocked SKU needs no replenishment -- correct empty state, not an error


# --------------------------------------------------------------------- #
# Promotion Intelligence
# --------------------------------------------------------------------- #
def test_build_upcoming_promotions_table():
    sku = "SKU-ABC-0001"
    promos = [{
        "promotion_id": "PROMO-0001", "sku": sku, "promotion_name": "Test Promo",
        "discount_percent": 20, "start_date": pd.Timestamp("2026-11-01"), "end_date": pd.Timestamp("2026-11-05"),
        "promotion_channel": "online",
    }]
    service, _, _ = _build_fixture(sku=sku, promotions=promos)
    orch = _orchestrator(service)
    df, error = data_prep.build_upcoming_promotions_table(orch, days_ahead=14)
    assert error is None
    assert "PROMO-0001" in df["promotion_id"].values


def test_build_promotion_readiness_flattening():
    sku = "SKU-ABC-0001"
    promos = [{
        "promotion_id": "PROMO-0001", "sku": sku, "promotion_name": "Test Promo",
        "discount_percent": 20, "start_date": pd.Timestamp("2026-11-01"), "end_date": pd.Timestamp("2026-11-05"),
        "promotion_channel": "online",
    }]
    service, _, _ = _build_fixture(sku=sku, store_available=0.0, sales_quantities=[10.0] * 60, promotions=promos)
    orch = _orchestrator(service)
    report, error = data_prep.build_promotion_readiness(orch, days_ahead=14)
    assert error is None
    flat = data_prep.flatten_readiness_report(report["reports"][0])
    assert flat["sku"] == sku
    assert flat["readiness_status"] in ("sufficient", "insufficient", "cannot_determine")


# --------------------------------------------------------------------- #
# Order Fulfillment
# --------------------------------------------------------------------- #
def test_build_orders_at_risk_table():
    orders = [_order_row("ORD-000001", "SKU-ABC-0001", 1, "PROCESSING", "ST-001", "2026-10-01")]  # overdue
    service, _, _ = _build_fixture(store_available=100.0, orders=orders)
    orch = _orchestrator(service)
    df, error = data_prep.build_orders_at_risk_table(orch)
    assert error is None
    assert "ORD-000001" in df["order_id"].values
    assert df.iloc[0]["risk_level"] == "critical"


def test_build_order_fulfillment_detail_unknown_order():
    service, _, _ = _build_fixture()
    orch = _orchestrator(service)
    detail, error = data_prep.build_order_fulfillment_detail(orch, "ORD-999999")
    assert error is None
    assert detail["order_found"] is False


def test_build_alternative_fulfillment_options():
    sku = "SKU-ABC-0001"
    orders = [_order_row("ORD-000002", sku, 5, "PROCESSING", "ST-001", "2026-11-05")]
    products = pd.DataFrame([{"sku": sku, "product_name": "W", "category": "Home", "brand": "X", "selling_price": 10.0, "cost_price": 5.0}])
    stores = pd.DataFrame([
        {"store_id": "ST-001", "store_name": "A", "city": "X", "region": "Y", "store_type": "Flagship"},
        {"store_id": "ST-002", "store_name": "B", "city": "X", "region": "Y", "store_type": "Flagship"},
    ])
    inventory = pd.DataFrame([
        {"sku": sku, "location_id": "ST-001", "location_type": "store", "on_hand_quantity": 1.0, "reserved_quantity": 0, "available_quantity": 1.0, "last_updated": "2026-10-27"},
        {"sku": sku, "location_id": "ST-002", "location_type": "store", "on_hand_quantity": 500.0, "reserved_quantity": 0, "available_quantity": 500.0, "last_updated": "2026-10-27"},
    ])
    service = FakeRetailDataService(products, stores, pd.DataFrame(columns=SALES_COLUMNS), inventory, pd.DataFrame(orders))
    orch = _orchestrator(service)
    df, result, error = data_prep.build_alternative_fulfillment_options(orch, "ORD-000002")
    assert error is None
    assert "ST-002" in df["location_id"].values


# --------------------------------------------------------------------- #
# Customer Experience
# --------------------------------------------------------------------- #
def test_build_customer_impact_risks_table():
    orders = [_order_row("ORD-000003", "SKU-ABC-0001", 1, "PROCESSING", "ST-001", "2026-10-01")]
    service, _, _ = _build_fixture(store_available=100.0, orders=orders)
    orch = _orchestrator(service)
    df, error = data_prep.build_customer_impact_risks_table(orch)
    assert error is None
    assert "ORD-000003" in df["order_id"].values
    # Only the synthetic customer_id is surfaced -- no other personal data exists to leak.
    assert set(df.columns) == {"order_id", "sku", "customer_id", "severity", "problem_type", "explanation", "potential_cancellation_risk"}


def test_build_customer_order_experience_detail():
    orders = [_order_row("ORD-000004", "SKU-ABC-0001", 1, "PROCESSING", "ST-001", "2026-10-01")]
    service, _, _ = _build_fixture(store_available=100.0, orders=orders)
    orch = _orchestrator(service)
    detail, error = data_prep.build_customer_order_experience_detail(orch, "ORD-000004")
    assert error is None
    assert detail["alternative_product_recommendation"]["available"] is False


# --------------------------------------------------------------------- #
# Ask Retail AI
# --------------------------------------------------------------------- #
def test_run_retail_query_empty_input():
    service, _, _ = _build_fixture()
    orch = _orchestrator(service)
    result, message = data_prep.run_retail_query(orch, "")
    assert result is None
    assert "enter a question" in message.lower()


def test_run_retail_query_no_api_key_needed(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    service, _, _ = _build_fixture()
    orch = _orchestrator(service)
    result, error = data_prep.run_retail_query(orch, "Give me today's retail risk summary.")
    assert error is None
    assert result["category"] == "cross_agent_retail_analysis"


# --------------------------------------------------------------------- #
# Empty datasets -- no crash anywhere
# --------------------------------------------------------------------- #
def test_all_builders_handle_empty_dataset_gracefully():
    service = FakeRetailDataService()
    orch = _orchestrator(service)

    df1, err1 = data_prep.build_inventory_table(orch)
    assert err1 is None and df1.empty

    df2, err2 = data_prep.build_orders_at_risk_table(orch)
    assert err2 is None and df2.empty

    df3, err3 = data_prep.build_upcoming_promotions_table(orch)
    assert err3 is None and df3.empty

    df4, err4 = data_prep.build_customer_impact_risks_table(orch)
    assert err4 is None and df4.empty

    data = data_prep.build_command_center(orch)
    assert data["fulfillment_summary"]["total_open_orders"] == 0


# --------------------------------------------------------------------- #
# Real-data smoke test
# --------------------------------------------------------------------- #
def test_against_real_project_data():
    orch = RetailIntelligenceOrchestrator()
    df, error = data_prep.build_inventory_table(orch)
    assert error is None
    assert len(df) > 0
