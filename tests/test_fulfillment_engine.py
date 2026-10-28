"""
Tests for order_fulfillment_agent/fulfillment_engine.py.

Uses the REAL InventoryRiskEngine and DemandForecastEngine (genuine
integration coverage) wired to a FakeRetailDataService with constructed
data, mirroring the fake-service pattern used throughout this project's
other agent test suites.
"""

import pandas as pd
import pytest

from order_fulfillment_agent.config import FulfillmentRiskSettings
from order_fulfillment_agent.fulfillment_engine import (
    OrderFulfillmentEngine,
    RISK_CRITICAL,
    RISK_HIGH,
    RISK_LOW,
    RISK_MEDIUM,
    RISK_NOT_APPLICABLE,
    RISK_UNABLE_TO_ASSESS,
    classify_order_risk,
)
from order_fulfillment_agent.llm_explainer import answer_question

SETTINGS = FulfillmentRiskSettings()

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


def _order_row(order_id, sku, quantity, status, fulfillment_location, promised_delivery_date, order_date="2026-10-01", customer_id="CUST-00001"):
    return {
        "order_id": order_id, "customer_id": customer_id,
        "order_date": pd.Timestamp(order_date), "sku": sku, "quantity": quantity,
        "order_status": status, "fulfillment_location": fulfillment_location,
        "promised_delivery_date": pd.Timestamp(promised_delivery_date) if promised_delivery_date else pd.NaT,
    }


def _daily_sales_rows(sku, store_id, start_date, quantities):
    dates = pd.date_range(start_date, periods=len(quantities))
    return pd.DataFrame({
        "transaction_id": [f"TXN-{sku}-{i}" for i in range(len(quantities))],
        "transaction_date": dates, "store_id": store_id, "sku": sku,
        "quantity_sold": quantities, "selling_price": 10.0, "sales_channel": "in_store",
    })


def _build_fixture(sku="SKU-ABC-0001", store_id="ST-001", warehouse_id="WH-01",
                    store_available=10.0, warehouse_on_hand=100.0, warehouse_reserved=0.0,
                    warehouse_inbound=0.0, supplier_lead_time_days=5, orders=None,
                    sales_quantities=None):
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
        "warehouse_id": warehouse_id, "sku": sku,
        "on_hand_quantity": warehouse_on_hand, "reserved_quantity": warehouse_reserved,
        "inbound_quantity": warehouse_inbound, "supplier_lead_time_days": supplier_lead_time_days,
    }])
    sales = _daily_sales_rows(sku, store_id, "2026-08-01", sales_quantities or [5.0] * 60)
    orders_df = pd.DataFrame(orders) if orders else pd.DataFrame(columns=ORDERS_COLUMNS)
    service = FakeRetailDataService(products, stores, sales, inventory, orders_df, warehouse)
    return service, sku, store_id, warehouse_id


def _engine(service, settings=None):
    return OrderFulfillmentEngine(service=service, settings=settings or SETTINGS)


REF = pd.Timestamp("2026-10-27")


# --------------------------------------------------------------------- #
# Pure classify_order_risk
# --------------------------------------------------------------------- #
def test_classify_future_date_sufficient_inventory_is_low():
    # Explicit guard: a future promised date with sufficient inventory
    # must never be escalated just because it hasn't shipped yet.
    assert classify_order_risk(True, False, False, True, False, 10, SETTINGS) == RISK_LOW


def test_classify_overdue_is_critical_regardless_of_inventory():
    assert classify_order_risk(True, False, True, True, False, None, SETTINGS) == RISK_CRITICAL
    assert classify_order_risk(True, False, True, False, False, None, SETTINGS) == RISK_CRITICAL


def test_classify_insufficient_inventory_escalates_with_time_pressure():
    assert classify_order_risk(True, False, False, False, False, 1, SETTINGS) == RISK_CRITICAL
    assert classify_order_risk(True, False, False, False, False, 3, SETTINGS) == RISK_HIGH
    assert classify_order_risk(True, False, False, False, False, 10, SETTINGS) == RISK_MEDIUM


def test_classify_missing_promised_date_is_unable_to_assess():
    assert classify_order_risk(True, True, False, True, False, None, SETTINGS) == RISK_UNABLE_TO_ASSESS


def test_classify_unknown_inventory_is_unable_to_assess():
    assert classify_order_risk(True, False, False, None, True, 5, SETTINGS) == RISK_UNABLE_TO_ASSESS


def test_classify_closed_order_is_not_applicable():
    assert classify_order_risk(False, False, False, True, False, 5, SETTINGS) == RISK_NOT_APPLICABLE


# --------------------------------------------------------------------- #
# Order with sufficient / insufficient inventory
# --------------------------------------------------------------------- #
def test_order_with_sufficient_inventory():
    orders = [_order_row("ORD-000001", "SKU-ABC-0001", 5, "PROCESSING", "ST-001", "2026-11-05")]
    service, sku, _, _ = _build_fixture(store_available=50.0, orders=orders)
    result = _engine(service).analyze_order_fulfillment("ORD-000001", reference_date=REF)
    assert result["inventory_readiness"]["sufficient"] is True
    assert result["risk_level"] == RISK_LOW


def test_order_with_insufficient_inventory():
    orders = [_order_row("ORD-000002", "SKU-ABC-0001", 50, "PROCESSING", "ST-001", "2026-11-05")]
    service, sku, _, _ = _build_fixture(store_available=5.0, orders=orders)
    result = _engine(service).analyze_order_fulfillment("ORD-000002", reference_date=REF)
    assert result["inventory_readiness"]["sufficient"] is False
    assert result["inventory_readiness"]["shortfall"] == 45.0
    assert result["risk_level"] in (RISK_CRITICAL, RISK_HIGH, RISK_MEDIUM)


# --------------------------------------------------------------------- #
# Past / future promised delivery date
# --------------------------------------------------------------------- #
def test_past_promised_delivery_date_is_critical():
    orders = [_order_row("ORD-000003", "SKU-ABC-0001", 1, "SHIPPED", "ST-001", "2026-10-01")]  # overdue
    service, _, _, _ = _build_fixture(store_available=100.0, orders=orders)
    result = _engine(service).analyze_order_fulfillment("ORD-000003", reference_date=REF)
    assert result["promised_date_passed"] is True
    assert result["days_overdue"] == 26
    assert result["risk_level"] == RISK_CRITICAL


def test_future_promised_delivery_date_with_good_inventory_is_low_not_flagged():
    orders = [_order_row("ORD-000004", "SKU-ABC-0001", 1, "PLACED", "ST-001", "2026-12-01")]
    service, _, _, _ = _build_fixture(store_available=100.0, orders=orders)
    result = _engine(service).analyze_order_fulfillment("ORD-000004", reference_date=REF)
    assert result["promised_date_passed"] is False
    assert result["risk_level"] == RISK_LOW


# --------------------------------------------------------------------- #
# Already delivered / cancelled orders
# --------------------------------------------------------------------- #
def test_already_delivered_order_is_not_applicable():
    orders = [_order_row("ORD-000005", "SKU-ABC-0001", 1, "DELIVERED", "ST-001", "2026-09-01")]
    service, _, _, _ = _build_fixture(orders=orders)
    result = _engine(service).analyze_order_fulfillment("ORD-000005", reference_date=REF)
    assert result["risk_level"] == RISK_NOT_APPLICABLE
    assert "actual_delivery_date" in result["note"]


def test_cancelled_order_is_not_applicable_and_excluded_from_bulk_risk():
    orders = [
        _order_row("ORD-000006", "SKU-ABC-0001", 1, "CANCELLED", "ST-001", "2026-09-01"),
        _order_row("ORD-000007", "SKU-ABC-0001", 1, "PLACED", "ST-001", "2026-12-01"),
    ]
    service, _, _, _ = _build_fixture(store_available=100.0, orders=orders)
    engine = _engine(service)
    single = engine.analyze_order_fulfillment("ORD-000006", reference_date=REF)
    assert single["risk_level"] == RISK_NOT_APPLICABLE

    at_risk = engine.get_orders_at_risk(reference_date=REF)
    assert all(r["order_id"] != "ORD-000006" for r in at_risk)


# --------------------------------------------------------------------- #
# Missing promised date / unknown order ID / missing SKU
# --------------------------------------------------------------------- #
def test_missing_promised_date_is_unable_to_assess():
    orders = [_order_row("ORD-000008", "SKU-ABC-0001", 1, "PROCESSING", "ST-001", None)]
    service, _, _, _ = _build_fixture(store_available=100.0, orders=orders)
    result = _engine(service).analyze_order_fulfillment("ORD-000008", reference_date=REF)
    assert result["promised_date_missing"] is True
    assert result["risk_level"] == RISK_UNABLE_TO_ASSESS


def test_unknown_order_id_is_graceful_not_an_error():
    service, _, _, _ = _build_fixture()
    result = _engine(service).analyze_order_fulfillment("ORD-999999")
    assert result["order_found"] is False
    assert "No order found" in result["note"]


def test_empty_or_none_order_id_raises_value_error():
    service, _, _, _ = _build_fixture()
    with pytest.raises(ValueError):
        _engine(service).analyze_order_fulfillment("")
    with pytest.raises(ValueError):
        _engine(service).analyze_order_fulfillment(None)


def test_missing_sku_on_order_row_handled_gracefully():
    # A SKU with NO inventory/warehouse rows anywhere (not even an empty
    # row at ST-001) -- the engine correctly distinguishes "no data point
    # exists for this sku at this location at all" from "confirmed zero at
    # a known location," rather than guessing either way.
    orders = [_order_row("ORD-000009", "SKU-NOT-REAL-0000", 1, "PROCESSING", "ST-001", "2026-11-05")]
    service, _, _, _ = _build_fixture(orders=orders)
    result = _engine(service).analyze_order_fulfillment("ORD-000009", reference_date=REF)
    assert result["inventory_readiness"]["eligible_available_at_location"] is None
    assert result["risk_level"] == RISK_UNABLE_TO_ASSESS


# --------------------------------------------------------------------- #
# Missing inventory data (unrecognized fulfillment_location)
# --------------------------------------------------------------------- #
def test_missing_inventory_data_unrecognized_location_is_unable_to_assess():
    orders = [_order_row("ORD-000010", "SKU-ABC-0001", 1, "PROCESSING", "ST-404", "2026-11-05")]
    service, _, _, _ = _build_fixture(store_available=100.0, orders=orders)
    result = _engine(service).analyze_order_fulfillment("ORD-000010", reference_date=REF)
    assert result["fulfillment_location_type"] == "unknown"
    assert result["risk_level"] == RISK_UNABLE_TO_ASSESS
    assert result["inventory_readiness"]["data_limitation"] is not None


# --------------------------------------------------------------------- #
# Alternative fulfillment: sufficient / insufficient stock
# --------------------------------------------------------------------- #
def test_alternative_location_with_sufficient_stock_is_candidate_requires_validation():
    sku = "SKU-ABC-0001"
    orders = [_order_row("ORD-000011", sku, 5, "PROCESSING", "ST-001", "2026-11-05")]
    products = pd.DataFrame([{"sku": sku, "product_name": "W", "category": "Home", "brand": "X", "selling_price": 10.0, "cost_price": 5.0}])
    stores = pd.DataFrame([
        {"store_id": "ST-001", "store_name": "A", "city": "X", "region": "Y", "store_type": "Flagship"},
        {"store_id": "ST-002", "store_name": "B", "city": "X", "region": "Y", "store_type": "Flagship"},
    ])
    inventory = pd.DataFrame([
        {"sku": sku, "location_id": "ST-001", "location_type": "store", "on_hand_quantity": 1.0, "reserved_quantity": 0, "available_quantity": 1.0, "last_updated": "2026-10-27"},
        {"sku": sku, "location_id": "ST-002", "location_type": "store", "on_hand_quantity": 500.0, "reserved_quantity": 0, "available_quantity": 500.0, "last_updated": "2026-10-27"},
    ])
    warehouse = pd.DataFrame(columns=WAREHOUSE_COLUMNS)
    service = FakeRetailDataService(products, stores, pd.DataFrame(columns=SALES_COLUMNS), inventory, pd.DataFrame(orders), warehouse)

    result = _engine(service).find_alternative_fulfillment_options("ORD-000011", reference_date=REF)
    store_002 = next(c for c in result["alternative_candidates"] if c["location_id"] == "ST-002")
    assert store_002["sufficient_stock"] is True
    assert store_002["feasibility"] == "candidate_requires_validation"


def test_alternative_location_with_insufficient_stock():
    sku = "SKU-ABC-0001"
    orders = [_order_row("ORD-000012", sku, 100, "PROCESSING", "ST-001", "2026-11-05")]
    products = pd.DataFrame([{"sku": sku, "product_name": "W", "category": "Home", "brand": "X", "selling_price": 10.0, "cost_price": 5.0}])
    stores = pd.DataFrame([
        {"store_id": "ST-001", "store_name": "A", "city": "X", "region": "Y", "store_type": "Flagship"},
        {"store_id": "ST-002", "store_name": "B", "city": "X", "region": "Y", "store_type": "Flagship"},
    ])
    inventory = pd.DataFrame([
        {"sku": sku, "location_id": "ST-001", "location_type": "store", "on_hand_quantity": 1.0, "reserved_quantity": 0, "available_quantity": 1.0, "last_updated": "2026-10-27"},
        {"sku": sku, "location_id": "ST-002", "location_type": "store", "on_hand_quantity": 3.0, "reserved_quantity": 0, "available_quantity": 3.0, "last_updated": "2026-10-27"},
    ])
    warehouse = pd.DataFrame(columns=WAREHOUSE_COLUMNS)
    service = FakeRetailDataService(products, stores, pd.DataFrame(columns=SALES_COLUMNS), inventory, pd.DataFrame(orders), warehouse)

    result = _engine(service).find_alternative_fulfillment_options("ORD-000012", reference_date=REF)
    store_002 = next(c for c in result["alternative_candidates"] if c["location_id"] == "ST-002")
    assert store_002["sufficient_stock"] is False
    assert store_002["feasibility"] == "insufficient_stock"


# --------------------------------------------------------------------- #
# Missing transit-time information
# --------------------------------------------------------------------- #
def test_delivery_feasibility_is_always_unknown_no_transit_data():
    orders = [_order_row("ORD-000013", "SKU-ABC-0001", 1, "PROCESSING", "ST-001", "2026-11-05")]
    service, _, _, _ = _build_fixture(store_available=100.0, orders=orders)
    result = _engine(service).analyze_order_fulfillment("ORD-000013", reference_date=REF)
    assert result["delivery_feasibility"]["status"] == "unknown"
    assert "no shipment tracking" in result["delivery_feasibility"]["reason"].lower() or "no transit" in result["delivery_feasibility"]["reason"].lower() or "transit-time" in result["delivery_feasibility"]["reason"].lower()


def test_warehouse_alternative_labels_lead_time_as_inbound_not_outbound():
    sku = "SKU-ABC-0001"
    orders = [_order_row("ORD-000014", sku, 5, "PROCESSING", "ST-001", "2026-11-05")]
    service, _, _, warehouse_id = _build_fixture(
        sku=sku, store_available=1.0, warehouse_on_hand=500.0, orders=orders, supplier_lead_time_days=10,
    )
    result = _engine(service).find_alternative_fulfillment_options("ORD-000014", reference_date=REF)
    wh_candidate = next(c for c in result["alternative_candidates"] if c["location_id"] == warehouse_id)
    assert wh_candidate["lead_time_known"] is True
    assert wh_candidate["lead_time_days"] == 10
    assert "inbound" in wh_candidate["note"].lower()


# --------------------------------------------------------------------- #
# Duplicate order lines
# --------------------------------------------------------------------- #
def test_duplicate_order_id_rows_handled_with_warning_not_a_crash():
    orders = [
        _order_row("ORD-000015", "SKU-ABC-0001", 5, "PROCESSING", "ST-001", "2026-11-05"),
        _order_row("ORD-000015", "SKU-ABC-0001", 5, "PROCESSING", "ST-001", "2026-11-05"),
    ]
    service, _, _, _ = _build_fixture(store_available=100.0, orders=orders)
    result = _engine(service).analyze_order_fulfillment("ORD-000015", reference_date=REF)
    assert result["order_found"] is True
    assert "data_quality_warning" in result
    assert "duplicate" in result["data_quality_warning"].lower()


# --------------------------------------------------------------------- #
# Reserved stock (already modeled via available_quantity / warehouse_available)
# --------------------------------------------------------------------- #
def test_reserved_stock_already_excluded_from_eligible_inventory():
    orders = [_order_row("ORD-000016", "SKU-ABC-0001", 5, "PROCESSING", "ST-001", "2026-11-05")]
    # on_hand=20, reserved=15 -> only 5 truly available; this must be what
    # the engine sees, not the raw on_hand figure.
    sku = "SKU-ABC-0001"
    store_id = "ST-001"
    products = pd.DataFrame([{"sku": sku, "product_name": "W", "category": "Home", "brand": "X", "selling_price": 10.0, "cost_price": 5.0}])
    stores = pd.DataFrame([{"store_id": store_id, "store_name": "A", "city": "X", "region": "Y", "store_type": "Flagship"}])
    inventory = pd.DataFrame([{
        "sku": sku, "location_id": store_id, "location_type": "store",
        "on_hand_quantity": 20.0, "reserved_quantity": 15.0, "available_quantity": 5.0, "last_updated": "2026-10-27",
    }])
    service = FakeRetailDataService(products, stores, pd.DataFrame(columns=SALES_COLUMNS), inventory, pd.DataFrame(orders))
    result = _engine(service).analyze_order_fulfillment("ORD-000016", reference_date=REF)
    assert result["inventory_readiness"]["eligible_available_at_location"] == 5.0
    assert result["inventory_readiness"]["sufficient"] is True  # exactly meets the 5 required
    assert result["inventory_readiness"]["provisional"] is True


# --------------------------------------------------------------------- #
# OpenAI API unavailable
# --------------------------------------------------------------------- #
def test_answer_question_works_without_api_key(monkeypatch):
    orders = [_order_row("ORD-000017", "SKU-ABC-0001", 1, "PROCESSING", "ST-001", "2026-11-05")]
    service, _, _, _ = _build_fixture(orders=orders)
    engine = _engine(service)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    result = answer_question("Which orders need attention today?", engine=engine)
    assert result["configured"] is False
    assert result["answer"] is None
    assert "OPENAI_API_KEY" in result["message"]


# --------------------------------------------------------------------- #
# Empty order dataset
# --------------------------------------------------------------------- #
def test_empty_order_dataset_does_not_crash_any_bulk_function():
    service, _, _, _ = _build_fixture(orders=None)
    engine = _engine(service)
    assert engine.get_orders_at_risk() == []
    assert engine.get_orders_due_today() == []
    assert engine.get_orders_with_inventory_shortages() == []
    assert engine.get_fulfillment_priorities() == []
    summary = engine.get_fulfillment_risk_summary()
    assert summary["total_open_orders"] == 0


# --------------------------------------------------------------------- #
# Registration with orchestration + real-data smoke test
# --------------------------------------------------------------------- #
def test_registered_with_orchestration_sharing_engines():
    from orchestration.service import RetailOrchestrationService
    orchestrator = RetailOrchestrationService()
    assert orchestrator.fulfillment_engine.service is orchestrator.service
    assert orchestrator.fulfillment_engine.inventory_engine is orchestrator.inventory_engine
    assert orchestrator.fulfillment_engine.demand_engine is orchestrator.demand_engine


def test_default_engine_runs_end_to_end_against_real_data():
    from order_fulfillment_agent.fulfillment_engine import get_fulfillment_risk_summary
    summary = get_fulfillment_risk_summary()
    assert summary["total_open_orders"] > 0
