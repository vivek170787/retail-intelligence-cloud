"""
Tests for orchestration/query_orchestrator.py (RetailIntelligenceOrchestrator).

Most tests exercise the REAL RetailOrchestrationService (and therefore the
real agent engines it wires) against a FakeRetailDataService -- genuine
integration coverage, not mocked logic. A few adversarial tests inject a
fake sub-engine on a real RetailOrchestrationService to prove graceful
degradation when a dependent agent fails.
"""

import pandas as pd
import pytest

from orchestration.query_orchestrator import (
    CATEGORY_CROSS_AGENT,
    CATEGORY_CUSTOMER_EXPERIENCE,
    CATEGORY_DEMAND,
    CATEGORY_FULFILLMENT,
    CATEGORY_INVENTORY,
    CATEGORY_PROMOTION,
    CATEGORY_REPLENISHMENT,
    RetailIntelligenceOrchestrator,
    WORKFLOW_CUSTOMER_EXPERIENCE_PROTECTION,
    WORKFLOW_EXECUTIVE_SUMMARY,
    WORKFLOW_PROMOTION_READINESS,
    WORKFLOW_STOCKOUT_PREVENTION,
    classify_query,
    normalize_severity,
    worst_severity,
)
from orchestration.service import RetailOrchestrationService

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
                    sales_quantities=None, orders=None):
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
    service = FakeRetailDataService(products, stores, sales, inventory, orders_df, warehouse)
    return service, sku, store_id


def _orchestrator(service):
    return RetailIntelligenceOrchestrator(orchestration_service=RetailOrchestrationService(service=service))


REF_QUERY_SUFFIX = ""  # reserved if a reference_date kwarg is added later


# --------------------------------------------------------------------- #
# Query classification (pure function)
# --------------------------------------------------------------------- #
def test_classify_each_supported_category():
    assert classify_query("What are the inventory and stockout risks?")[0] == CATEGORY_INVENTORY
    assert classify_query("What is the demand forecast for next week?")[0] == CATEGORY_DEMAND
    assert classify_query("Which SKUs need replenishment?")[0] == CATEGORY_REPLENISHMENT
    assert classify_query("Is inventory ready for promotions?")[0] == CATEGORY_PROMOTION
    assert classify_query("Which orders have fulfillment risk?")[0] == CATEGORY_FULFILLMENT
    assert classify_query("Which orders have customer experience risk?")[0] == CATEGORY_CUSTOMER_EXPERIENCE
    assert classify_query("Give me an executive retail summary")[0] == CATEGORY_CROSS_AGENT


def test_classify_cross_agent_workflows():
    assert classify_query("Run stockout prevention analysis")[1] == WORKFLOW_STOCKOUT_PREVENTION
    assert classify_query("Run the promotion readiness workflow")[1] == WORKFLOW_PROMOTION_READINESS
    assert classify_query("How can we protect customer experience?")[1] == WORKFLOW_CUSTOMER_EXPERIENCE_PROTECTION
    assert classify_query("Give me a business overview")[1] == WORKFLOW_EXECUTIVE_SUMMARY


def test_severity_normalization_and_worst_severity():
    assert normalize_severity("insufficient") == "high"
    assert normalize_severity("sufficient") == "low"
    assert normalize_severity("cannot_determine") == "unable_to_assess"
    assert normalize_severity("totally_unrecognized_value") == "unable_to_assess"
    assert worst_severity(["low", "critical", "medium"]) == "critical"
    assert worst_severity([]) == "unable_to_assess"


# --------------------------------------------------------------------- #
# Each supported query category -- end-to-end against a fixture
# --------------------------------------------------------------------- #
def test_inventory_category_query():
    service, sku, _ = _build_fixture(store_available=0.0, sales_quantities=[10.0] * 60)
    result = _orchestrator(service).handle_query(f"What is the inventory risk for {sku}?")
    assert result["category"] == CATEGORY_INVENTORY
    assert sku in result["affected_entities"]["skus"]
    assert result["severity"] == "critical"
    assert result["agents_used"] == ["inventory"]


def test_demand_category_query():
    service, sku, _ = _build_fixture()
    result = _orchestrator(service).handle_query(f"What is the demand forecast for {sku}?")
    assert result["category"] == CATEGORY_DEMAND
    assert result["agents_used"] == ["demand"]


def test_replenishment_category_query():
    service, sku, _ = _build_fixture(store_available=0.0, sales_quantities=[10.0] * 60)
    result = _orchestrator(service).handle_query(f"Does {sku} need replenishment?")
    assert result["category"] == CATEGORY_REPLENISHMENT
    assert result["agents_used"] == ["inventory"]


def test_promotion_category_query():
    service, sku, _ = _build_fixture()
    result = _orchestrator(service).handle_query(f"Is there a promotion risk for {sku}?")
    assert result["category"] == CATEGORY_PROMOTION
    assert result["agents_used"] == ["promotion"]


def test_fulfillment_category_query():
    orders = [_order_row("ORD-000001", "SKU-ABC-0001", 1, "PROCESSING", "ST-001", "2026-10-01")]
    service, _, _ = _build_fixture(store_available=100.0, orders=orders)
    result = _orchestrator(service).handle_query("Which orders have fulfillment risk?")
    assert result["category"] == CATEGORY_FULFILLMENT
    assert result["agents_used"] == ["fulfillment", "fulfillment"]


def test_customer_experience_category_query():
    orders = [_order_row("ORD-000002", "SKU-ABC-0001", 1, "PROCESSING", "ST-001", "2026-10-01")]
    service, _, _ = _build_fixture(store_available=100.0, orders=orders)
    result = _orchestrator(service).handle_query("Which orders have customer experience risk?")
    assert result["category"] == CATEGORY_CUSTOMER_EXPERIENCE
    assert result["agents_used"] == ["customer_experience", "customer_experience"]


def test_cross_agent_executive_summary_category_query():
    service, _, _ = _build_fixture()
    result = _orchestrator(service).handle_query("Give me an executive retail summary")
    assert result["category"] == CATEGORY_CROSS_AGENT
    assert set(result["agents_used"]) == {"inventory", "demand", "promotion", "fulfillment", "customer_experience"}


# --------------------------------------------------------------------- #
# Cross-agent workflows (Examples A-D)
# --------------------------------------------------------------------- #
def test_stockout_prevention_workflow_single_sku():
    service, sku, _ = _build_fixture(store_available=0.0, sales_quantities=[10.0] * 60)
    result = _orchestrator(service).stockout_prevention_workflow(sku=sku)
    assert "inventory" in result["agents_used"]
    assert "demand" in result["agents_used"]
    assert sku in result["affected_entities"]["skus"]


def test_promotion_readiness_workflow_adds_replenishment_feasibility():
    sku = "SKU-ABC-0001"
    promotions = pd.DataFrame([{
        "promotion_id": "PROMO-0001", "sku": sku, "promotion_name": "Test Promo",
        "discount_percent": 20, "start_date": pd.Timestamp("2026-10-30"), "end_date": pd.Timestamp("2026-11-02"),
        "promotion_channel": "online",
    }])
    service, _, _ = _build_fixture(sku=sku, store_available=0.0, sales_quantities=[10.0] * 60)
    service.promotions_df = promotions
    result = _orchestrator(service).promotion_readiness_workflow()
    assert "promotion" in result["agents_used"]
    assert "replenishment_feasibility" in result["evidence"]


def test_customer_experience_protection_workflow():
    orders = [_order_row("ORD-000003", "SKU-ABC-0001", 1, "PROCESSING", "ST-001", "2026-10-01")]
    service, _, _ = _build_fixture(store_available=100.0, orders=orders)
    result = _orchestrator(service).customer_experience_protection_workflow()
    assert "customer_experience" in result["agents_used"]
    assert "ORD-000003" in result["affected_entities"]["orders"]


def test_executive_retail_summary_workflow_combines_all_five():
    service, _, _ = _build_fixture()
    result = _orchestrator(service).executive_retail_summary_workflow()
    assert set(result["agents_used"]) == {"inventory", "demand", "promotion", "fulfillment", "customer_experience"}
    assert len(result["key_findings"]) == 5


class _FailingInventoryEngineForPromotion:
    """Fails inventory in a way that doesn't raise ValueError, so
    promotion_agent's own per-item resilience silently absorbs it into
    cannot_determine rather than propagating -- this must still be
    surfaced honestly at the executive-summary level, not hidden behind
    a falsely-reassuring '0 insufficient'."""

    def get_product_inventory_analysis(self, sku):
        raise RuntimeError("simulated inventory agent outage")


def test_executive_summary_surfaces_silently_undetermined_promotions():
    sku = "SKU-ABC-0001"
    promotions = pd.DataFrame([{
        "promotion_id": "PROMO-0001", "sku": sku, "promotion_name": "Test Promo",
        "discount_percent": 20, "start_date": pd.Timestamp("2026-10-30"), "end_date": pd.Timestamp("2026-11-02"),
        "promotion_channel": "online",
    }])
    service, _, _ = _build_fixture(sku=sku)
    service.promotions_df = promotions
    svc = RetailOrchestrationService(service=service, inventory_engine=_FailingInventoryEngineForPromotion())
    orchestrator = RetailIntelligenceOrchestrator(orchestration_service=svc)

    result = orchestrator.executive_retail_summary_workflow()
    promo_finding = next(f for f in result["key_findings"] if f.startswith("Promotions:"))
    assert "could not be assessed" in promo_finding
    assert "1 could not be assessed" in promo_finding
    assert any("could not be determined" in g for g in result["data_gaps_and_uncertainty"])
    assert result["severity"] == "unable_to_assess"


# --------------------------------------------------------------------- #
# Missing or failing agents (graceful degradation)
# --------------------------------------------------------------------- #
class _AlwaysFailingInventoryEngine:
    def get_inventory_summary(self):
        raise RuntimeError("simulated inventory agent failure")

    def get_top_stockout_risks(self, limit=10):
        raise RuntimeError("simulated inventory agent failure")

    def get_product_inventory_analysis(self, sku):
        raise RuntimeError("simulated inventory agent failure")

    def get_replenishment_recommendations(self):
        raise RuntimeError("simulated inventory agent failure")


def test_failing_inventory_agent_degrades_gracefully_not_a_crash():
    service, _, _ = _build_fixture()
    svc = RetailOrchestrationService(service=service, inventory_engine=_AlwaysFailingInventoryEngine())
    orchestrator = RetailIntelligenceOrchestrator(orchestration_service=svc)

    result = orchestrator.handle_query("What are the inventory risks?")
    assert result["severity"] == "unable_to_assess"
    assert any("inventory agent unavailable" in g.lower() for g in result["data_gaps_and_uncertainty"])


class _PartiallyMissingInventoryEngine:
    """Missing get_inventory_summary entirely -- not just a method that
    raises when called. _safe_call must resolve the method INSIDE its own
    try block, or this raises AttributeError in the caller's frame before
    the helper is ever entered (the exact bug this test guards against)."""

    def get_top_stockout_risks(self, limit=10):
        return []


def test_agent_missing_a_method_entirely_degrades_gracefully():
    service, _, _ = _build_fixture()
    svc = RetailOrchestrationService(service=service, inventory_engine=_PartiallyMissingInventoryEngine())
    orchestrator = RetailIntelligenceOrchestrator(orchestration_service=svc)

    result = orchestrator.handle_query("What are the inventory risks?")  # must not raise AttributeError
    assert result["severity"] == "unable_to_assess"
    assert any("no attribute" in g.lower() for g in result["data_gaps_and_uncertainty"])


def test_executive_summary_survives_one_failing_agent():
    service, _, _ = _build_fixture()
    svc = RetailOrchestrationService(service=service, inventory_engine=_AlwaysFailingInventoryEngine())
    orchestrator = RetailIntelligenceOrchestrator(orchestration_service=svc)

    result = orchestrator.executive_retail_summary_workflow()
    assert any("inventory agent unavailable" in g.lower() for g in result["data_gaps_and_uncertainty"])
    # The other four agents' findings must still be present.
    assert len(result["key_findings"]) == 4


# --------------------------------------------------------------------- #
# Empty results / empty datasets
# --------------------------------------------------------------------- #
def test_empty_dataset_does_not_crash_any_category():
    service, _, _ = _build_fixture(orders=None)
    service.orders_df = pd.DataFrame(columns=ORDERS_COLUMNS)
    service.promotions_df = pd.DataFrame(columns=PROMOTIONS_COLUMNS)
    orchestrator = _orchestrator(service)

    for query in [
        "What are the inventory risks?",
        "What is the demand outlook?",
        "Which SKUs need replenishment?",
        "What is promotion readiness?",
        "Which orders have fulfillment risk?",
        "Which orders have customer experience risk?",
        "Give me an executive summary",
    ]:
        result = orchestrator.handle_query(query)
        assert isinstance(result, dict)
        assert "severity" in result


# --------------------------------------------------------------------- #
# Invalid queries
# --------------------------------------------------------------------- #
def test_empty_or_none_query_raises_value_error():
    service, _, _ = _build_fixture()
    orchestrator = _orchestrator(service)
    with pytest.raises(ValueError):
        orchestrator.handle_query("")
    with pytest.raises(ValueError):
        orchestrator.handle_query(None)


# --------------------------------------------------------------------- #
# Missing OpenAI API key -- handle_query never needs one
# --------------------------------------------------------------------- #
def test_handle_query_never_requires_openai_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    service, _, _ = _build_fixture()
    orchestrator = _orchestrator(service)
    result = orchestrator.handle_query("Give me an executive retail summary")
    assert isinstance(result, dict)
    assert result["category"] == CATEGORY_CROSS_AGENT


# --------------------------------------------------------------------- #
# Consistent output structure across every category
# --------------------------------------------------------------------- #
REQUIRED_RESPONSE_KEYS = {
    "query", "category", "summary", "key_findings", "affected_entities", "severity",
    "evidence", "recommended_actions", "data_gaps_and_uncertainty", "agents_used",
    "human_approval_required", "disclaimer",
}


def test_response_structure_is_consistent_across_categories():
    orders = [_order_row("ORD-000004", "SKU-ABC-0001", 1, "PROCESSING", "ST-001", "2026-10-01")]
    service, sku, _ = _build_fixture(store_available=100.0, orders=orders)
    orchestrator = _orchestrator(service)

    queries = [
        "What are the inventory risks?",
        "What is the demand forecast?",
        "Which SKUs need replenishment?",
        "What is promotion readiness?",
        "Which orders have fulfillment risk?",
        "Which orders have customer experience risk?",
        "Give me an executive summary",
    ]
    for q in queries:
        result = orchestrator.handle_query(q)
        assert REQUIRED_RESPONSE_KEYS.issubset(result.keys()), f"missing keys for query: {q!r}"
        assert isinstance(result["affected_entities"], dict)
        assert set(result["affected_entities"].keys()) == {"skus", "stores", "orders"}


# --------------------------------------------------------------------- #
# Prevention of unsupported claims and operational side effects
# --------------------------------------------------------------------- #
def test_human_approval_required_is_always_true():
    service, _, _ = _build_fixture()
    orchestrator = _orchestrator(service)
    result = orchestrator.handle_query("Give me an executive retail summary")
    assert result["human_approval_required"] is True
    assert "human approval" in result["disclaimer"].lower()


def test_response_never_claims_an_action_was_taken():
    orders = [_order_row("ORD-000005", "SKU-ABC-0001", 1, "PROCESSING", "ST-001", "2026-10-01")]
    service, _, _ = _build_fixture(store_available=0.0, orders=orders)
    orchestrator = _orchestrator(service)
    forbidden_phrases = ("order placed", "transfer completed", "inventory transferred", "refund issued", "promotion activated")
    for q in ["Which orders have fulfillment risk?", "Give me an executive retail summary"]:
        result = orchestrator.handle_query(q)
        combined_text = " ".join(result["recommended_actions"]).lower() + result["disclaimer"].lower()
        assert not any(phrase in combined_text for phrase in forbidden_phrases)


# --------------------------------------------------------------------- #
# Shared-service / no-duplicate-loading check + real-data smoke test
# --------------------------------------------------------------------- #
def test_orchestrator_reuses_the_same_underlying_engines_no_duplication():
    service, _, _ = _build_fixture()
    svc = RetailOrchestrationService(service=service)
    orchestrator = RetailIntelligenceOrchestrator(orchestration_service=svc)
    assert orchestrator.svc is svc
    assert orchestrator.svc.inventory_engine is svc.inventory_engine


def test_default_orchestrator_runs_end_to_end_against_real_data():
    from orchestration.query_orchestrator import handle_query
    result = handle_query("Give me an executive retail summary")
    assert result["category"] == CATEGORY_CROSS_AGENT
    assert len(result["key_findings"]) == 5
