"""
Tests for customer_experience_agent/cx_engine.py.

Uses the REAL OrderFulfillmentEngine (and the real InventoryRiskEngine/
DemandForecastEngine it wires internally) against a FakeRetailDataService,
mirroring the fake-service pattern used throughout this project's other
agent test suites -- genuine integration coverage, not mocked logic.
A couple of adversarial tests inject a fake fulfillment_engine directly,
since those failure modes can't be triggered through correct real-agent
behavior.
"""

import pandas as pd
import pytest

from customer_experience_agent.cx_engine import (
    CustomerExperienceEngine,
    PROBLEM_CONFIRMED,
    PROBLEM_NONE,
    PROBLEM_PREDICTED,
    PROBLEM_UNKNOWN,
    assess_cancellation_risk,
    build_recommended_actions,
    classify_problem_type,
)
from customer_experience_agent.llm_explainer import answer_question
from order_fulfillment_agent.fulfillment_engine import OrderFulfillmentEngine

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


def _build_fixture(sku="SKU-ABC-0001", store_id="ST-001", store_available=10.0,
                    orders=None, marketplace=None):
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
    sales = _daily_sales_rows(sku, store_id, "2026-08-01", [5.0] * 60)
    orders_df = pd.DataFrame(orders) if orders else pd.DataFrame(columns=ORDERS_COLUMNS)
    marketplace_df = pd.DataFrame(marketplace) if marketplace else pd.DataFrame(columns=MARKETPLACE_COLUMNS)
    service = FakeRetailDataService(products, stores, sales, inventory, orders_df, marketplace=marketplace_df)
    return service, sku, store_id


def _engine(service):
    fulfillment_engine = OrderFulfillmentEngine(service=service)
    return CustomerExperienceEngine(service=service, fulfillment_engine=fulfillment_engine)


REF = pd.Timestamp("2026-10-27")


# --------------------------------------------------------------------- #
# Pure functions
# --------------------------------------------------------------------- #
def test_classify_problem_type_confirmed_vs_predicted():
    confirmed_input = {"risk_level": "critical", "promised_date_passed": True, "inventory_readiness": {"sufficient": False}}
    predicted_input = {"risk_level": "medium", "promised_date_passed": False, "inventory_readiness": {"sufficient": False}}
    none_input = {"risk_level": "low", "promised_date_passed": False, "inventory_readiness": {"sufficient": True}}
    assert classify_problem_type(confirmed_input) == PROBLEM_CONFIRMED
    assert classify_problem_type(predicted_input) == PROBLEM_PREDICTED
    assert classify_problem_type(none_input) == PROBLEM_NONE


def test_classify_problem_type_unable_to_assess_is_unknown():
    unable_input = {"risk_level": "unable_to_assess", "promised_date_passed": None, "inventory_readiness": {"sufficient": None}}
    assert classify_problem_type(unable_input) == PROBLEM_UNKNOWN


def test_assess_cancellation_risk_requires_full_evidence():
    base = {"risk_level": "critical", "promised_date_passed": True, "inventory_readiness": {"sufficient": False}}
    flagged, reason = assess_cancellation_risk(base, alternatives_found=False)
    assert flagged is True
    assert "human review" in reason

    # Alternative found -> not flagged.
    flagged2, _ = assess_cancellation_risk(base, alternatives_found=True)
    assert flagged2 is False

    # Not critical -> never flagged regardless of other evidence.
    medium = {"risk_level": "medium", "promised_date_passed": True, "inventory_readiness": {"sufficient": False}}
    flagged3, _ = assess_cancellation_risk(medium, alternatives_found=False)
    assert flagged3 is False


def test_build_recommended_actions_never_includes_unsupported_claims():
    actions = build_recommended_actions(PROBLEM_CONFIRMED, inventory_sufficient=False, severity="critical")
    assert "Route unresolved issue to customer support." in actions
    assert "Check eligible inventory at alternative locations." in actions
    assert all("cancel" not in a.lower() and "refund" not in a.lower() for a in actions)


# --------------------------------------------------------------------- #
# Delayed / at-risk orders (confirmed problem)
# --------------------------------------------------------------------- #
def test_delayed_order_is_confirmed_problem_critical():
    orders = [_order_row("ORD-000001", "SKU-ABC-0001", 1, "PROCESSING", "ST-001", "2026-10-01")]  # overdue
    service, _, _ = _build_fixture(store_available=100.0, orders=orders)
    result = _engine(service).analyze_customer_order_experience("ORD-000001", reference_date=REF)
    assert result["problem_type"] == PROBLEM_CONFIRMED
    assert result["severity"] == "critical"
    assert "already passed" in result["explanation"]


# --------------------------------------------------------------------- #
# Sufficient / insufficient inventory
# --------------------------------------------------------------------- #
def test_sufficient_inventory_future_date_is_healthy():
    orders = [_order_row("ORD-000002", "SKU-ABC-0001", 1, "PLACED", "ST-001", "2026-12-01")]
    service, _, _ = _build_fixture(store_available=100.0, orders=orders)
    result = _engine(service).analyze_customer_order_experience("ORD-000002", reference_date=REF)
    assert result["severity"] == "low"
    assert result["problem_type"] == PROBLEM_NONE


def test_insufficient_inventory_future_date_is_predicted_risk():
    orders = [_order_row("ORD-000003", "SKU-ABC-0001", 50, "PROCESSING", "ST-001", "2026-11-20")]
    service, _, _ = _build_fixture(store_available=2.0, orders=orders)
    result = _engine(service).analyze_customer_order_experience("ORD-000003", reference_date=REF)
    assert result["problem_type"] == PROBLEM_PREDICTED
    assert "predicted risk, not a confirmed problem" in result["explanation"]


# --------------------------------------------------------------------- #
# Delivered / cancelled orders
# --------------------------------------------------------------------- #
def test_delivered_order_not_applicable():
    orders = [_order_row("ORD-000004", "SKU-ABC-0001", 1, "DELIVERED", "ST-001", "2026-09-01")]
    service, _, _ = _build_fixture(orders=orders)
    result = _engine(service).analyze_customer_order_experience("ORD-000004", reference_date=REF)
    assert result["severity"] == "not_applicable"
    assert result["recommended_actions"] == []


def test_cancelled_order_excluded_from_impact_risks():
    orders = [
        _order_row("ORD-000005", "SKU-ABC-0001", 1, "CANCELLED", "ST-001", "2026-09-01"),
        _order_row("ORD-000006", "SKU-ABC-0001", 1, "PLACED", "ST-001", "2026-12-01"),
    ]
    service, _, _ = _build_fixture(store_available=100.0, orders=orders)
    risks = _engine(service).get_customer_impact_risks(reference_date=REF)
    assert all(r["order_id"] != "ORD-000005" for r in risks)


# --------------------------------------------------------------------- #
# Missing delivery dates / inventory data
# --------------------------------------------------------------------- #
def test_missing_promised_date_is_unable_to_assess():
    orders = [_order_row("ORD-000007", "SKU-ABC-0001", 1, "PROCESSING", "ST-001", None)]
    service, _, _ = _build_fixture(store_available=100.0, orders=orders)
    result = _engine(service).analyze_customer_order_experience("ORD-000007", reference_date=REF)
    assert result["severity"] == "unable_to_assess"
    assert any("promised_delivery_date is missing" in m for m in result["missing_information"])


def test_missing_inventory_data_unrecognized_location_unable_to_assess():
    orders = [_order_row("ORD-000008", "SKU-ABC-0001", 1, "PROCESSING", "ST-404", "2026-11-05")]
    service, _, _ = _build_fixture(store_available=100.0, orders=orders)
    result = _engine(service).analyze_customer_order_experience("ORD-000008", reference_date=REF)
    assert result["severity"] == "unable_to_assess"
    assert any("not found in store or warehouse" in m for m in result["missing_information"])


# --------------------------------------------------------------------- #
# Unknown order IDs
# --------------------------------------------------------------------- #
def test_unknown_order_id_graceful():
    service, _, _ = _build_fixture()
    result = _engine(service).analyze_customer_order_experience("ORD-999999")
    assert result["order_found"] is False


def test_empty_order_id_raises_value_error():
    service, _, _ = _build_fixture()
    with pytest.raises(ValueError):
        _engine(service).analyze_customer_order_experience("")


# --------------------------------------------------------------------- #
# Empty datasets
# --------------------------------------------------------------------- #
def test_empty_order_dataset_does_not_crash():
    service, _, _ = _build_fixture(orders=None)
    engine = _engine(service)
    assert engine.get_customer_impact_risks() == []
    assert engine.get_at_risk_customer_orders() == []
    recovery = engine.get_service_recovery_recommendations()
    assert recovery["total_orders_with_recommendations"] == 0
    summary = engine.get_customer_experience_summary()
    assert summary["total_customer_impact_risks"] == 0


# --------------------------------------------------------------------- #
# Missing OpenAI API key
# --------------------------------------------------------------------- #
def test_answer_question_works_without_api_key(monkeypatch):
    orders = [_order_row("ORD-000009", "SKU-ABC-0001", 1, "PROCESSING", "ST-001", "2026-10-01")]
    service, _, _ = _build_fixture(store_available=100.0, orders=orders)
    engine = _engine(service)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    result = answer_question("Which orders need attention today?", engine=engine)
    assert result["configured"] is False
    assert result["answer"] is None
    assert "OPENAI_API_KEY" in result["message"]


# --------------------------------------------------------------------- #
# Failures in dependent agents
# --------------------------------------------------------------------- #
class _AlwaysFailingFulfillmentEngine:
    def get_orders_at_risk(self, reference_date=None):
        return [{"order_id": "ORD-000010"}]

    def get_fulfillment_priorities(self, limit=10, reference_date=None):
        return [{"order_id": "ORD-000010"}]

    def analyze_order_fulfillment(self, order_id, reference_date=None):
        raise RuntimeError(f"simulated fulfillment agent failure for {order_id}")


def test_dependent_agent_failure_is_isolated_not_a_crash():
    service, _, _ = _build_fixture()
    engine = CustomerExperienceEngine(service=service, fulfillment_engine=_AlwaysFailingFulfillmentEngine())

    risks = engine.get_customer_impact_risks()
    assert len(risks) == 1
    assert risks[0]["error"] is not None
    assert risks[0]["severity"] == "unable_to_assess"

    with pytest.raises(RuntimeError):
        engine.analyze_customer_order_experience("ORD-000010")


# --------------------------------------------------------------------- #
# Marketplace availability context (new capability this agent adds)
# --------------------------------------------------------------------- #
def test_marketplace_availability_issue_surfaced_as_context_only():
    sku = "SKU-ABC-0001"
    orders = [_order_row("ORD-000011", sku, 50, "PROCESSING", "ST-001", "2026-11-20")]
    marketplace = [
        {"marketplace": "Amazon", "listing_id": "LST-1", "sku": sku, "listing_status": "OUT_OF_STOCK", "listed_price": 10.0, "available_quantity": 0},
        {"marketplace": "Flipkart", "listing_id": "LST-2", "sku": sku, "listing_status": "ACTIVE", "listed_price": 10.0, "available_quantity": 20},
    ]
    service, _, _ = _build_fixture(store_available=2.0, orders=orders, marketplace=marketplace)
    result = _engine(service).analyze_customer_order_experience("ORD-000011", reference_date=REF)
    ctx = result["marketplace_context"]
    assert ctx["any_availability_issue"] is True
    assert "Amazon" in ctx["affected_marketplaces"]
    assert "not necessarily tied to this specific order" in ctx["note"]


def test_no_marketplace_listings_returns_no_issue():
    orders = [_order_row("ORD-000012", "SKU-ABC-0001", 1, "PROCESSING", "ST-001", "2026-12-01")]
    service, _, _ = _build_fixture(store_available=100.0, orders=orders)
    result = _engine(service).analyze_customer_order_experience("ORD-000012", reference_date=REF)
    ctx = result["marketplace_context"]
    assert ctx["has_marketplace_listings"] is False
    assert ctx["any_availability_issue"] is False


# --------------------------------------------------------------------- #
# Alternative-product and policy-action are always honestly unsupported
# --------------------------------------------------------------------- #
def test_alternative_product_recommendation_always_unsupported():
    orders = [_order_row("ORD-000013", "SKU-ABC-0001", 1, "PROCESSING", "ST-001", "2026-12-01")]
    service, _, _ = _build_fixture(store_available=100.0, orders=orders)
    result = _engine(service).analyze_customer_order_experience("ORD-000013", reference_date=REF)
    assert result["alternative_product_recommendation"]["available"] is False
    assert "no product substitutability" in result["alternative_product_recommendation"]["reason"].lower()


def test_human_reviewed_recovery_action_never_names_a_specific_action():
    orders = [_order_row("ORD-000014", "SKU-ABC-0001", 1, "PROCESSING", "ST-001", "2026-10-01")]  # overdue -> critical
    service, _, _ = _build_fixture(store_available=100.0, orders=orders)
    result = _engine(service).analyze_customer_order_experience("ORD-000014", reference_date=REF)
    assert result["human_reviewed_recovery_action"]["suggested"] is True
    assert result["human_reviewed_recovery_action"]["specific_action"] is None


# --------------------------------------------------------------------- #
# Registration with orchestration + real-data smoke test
# --------------------------------------------------------------------- #
def test_registered_with_orchestration_sharing_engines():
    from orchestration.service import RetailOrchestrationService
    orchestrator = RetailOrchestrationService()
    assert orchestrator.cx_engine.service is orchestrator.service
    assert orchestrator.cx_engine.fulfillment_engine is orchestrator.fulfillment_engine


def test_default_engine_runs_end_to_end_against_real_data():
    from customer_experience_agent.cx_engine import get_customer_experience_summary
    summary = get_customer_experience_summary()
    assert summary["total_customer_impact_risks"] >= 0
