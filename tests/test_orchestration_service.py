"""
Tests for orchestration/service.py.

Most tests use the REAL InventoryRiskEngine and DemandForecastEngine
(genuine integration coverage of the actual agent logic) wired to a
FakeRetailDataService with constructed data, mirroring the fake-service
pattern in test_inventory_risk_engine.py / test_demand_forecasting_engine.py.
A couple of adversarial tests (SKU mismatch, an agent raising unexpectedly)
inject fake engine stand-ins directly, since those failure modes can't be
triggered through the real agents' own correct behavior.
"""

import pandas as pd
import pytest

from inventory_agent.risk_engine import InventoryRiskEngine
from demand_forecasting_agent.forecasting_engine import DemandForecastEngine
from orchestration.service import RetailOrchestrationService
from orchestration.llm_explainer import answer_question

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
    """Combined RetailDataService stand-in covering everything both
    InventoryRiskEngine and DemandForecastEngine need."""

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

    def get_promotions(self, sku):
        sku = _validate_sku(sku)
        return self.promotions_df[self.promotions_df["sku"] == sku].reset_index(drop=True)


def _daily_sales_rows(sku, store_id, start_date, quantities):
    dates = pd.date_range(start_date, periods=len(quantities))
    return pd.DataFrame({
        "transaction_id": [f"TXN-{sku}-{i}" for i in range(len(quantities))],
        "transaction_date": dates, "store_id": store_id, "sku": sku,
        "quantity_sold": quantities, "selling_price": 10.0, "sales_channel": "in_store",
    })


def _build_fixture(sku="SKU-TEST-0001", store_id="ST-001", quantities=None,
                    store_available=10.0, warehouse_on_hand=100.0, warehouse_reserved=0.0,
                    warehouse_inbound=0.0, supplier_lead_time_days=7):
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
    service = FakeRetailDataService(products, stores, sales, inventory, orders, warehouse)
    return service, sku, store_id


def _orchestrator(service):
    return RetailOrchestrationService(service=service)


# --------------------------------------------------------------------- #
# 1. Both agents returning valid results
# --------------------------------------------------------------------- #
def test_both_agents_return_valid_results():
    service, sku, _ = _build_fixture(quantities=[10.0] * 30, store_available=50.0)
    result = _orchestrator(service).analyze_inventory_vs_forecast(sku=sku, horizon_days=7)
    assert result["forecast"]["sufficient_data"] is True
    assert result["forecast"]["total_demand"] == pytest.approx(70.0)
    assert result["inventory"]["current_available"] == 50.0
    assert result["demand_gap"] == pytest.approx(20.0)  # 70 - 50


# --------------------------------------------------------------------- #
# 2. Unknown SKU
# --------------------------------------------------------------------- #
def test_unknown_but_well_formed_sku_is_graceful():
    service, _, _ = _build_fixture()
    result = _orchestrator(service).analyze_inventory_vs_forecast(sku="SKU-NOT-REAL")
    assert any("not found in the product catalog" in w for w in result["data_quality_warnings"])
    assert result["requires_investigation"] is True


def test_empty_or_none_sku_raises_value_error():
    service, _, _ = _build_fixture()
    orchestrator = _orchestrator(service)
    with pytest.raises(ValueError):
        orchestrator.analyze_inventory_vs_forecast(sku="")


# --------------------------------------------------------------------- #
# 3. Missing inventory
# --------------------------------------------------------------------- #
def test_missing_inventory_gives_zero_available_not_a_crash():
    sku = "SKU-TEST-0001"
    store_id = "ST-001"
    products = pd.DataFrame([{"sku": sku, "product_name": "No Inventory Widget", "category": "Home", "brand": "X", "selling_price": 10.0, "cost_price": 5.0}])
    stores = pd.DataFrame([{"store_id": store_id, "store_name": "A", "city": "X", "region": "Y", "store_type": "Flagship"}])
    sales = _daily_sales_rows(sku, store_id, "2026-09-01", [5.0] * 30)
    service = FakeRetailDataService(products, stores, sales)  # no inventory rows at all
    result = _orchestrator(service).analyze_inventory_vs_forecast(sku=sku)
    assert result["inventory"]["current_available"] == 0.0
    assert result["demand_gap"] == pytest.approx(35.0)  # 35 - 0
    assert result["requires_investigation"] is True


# --------------------------------------------------------------------- #
# 4. Missing forecast data
# --------------------------------------------------------------------- #
def test_missing_forecast_data_insufficient_history():
    service, sku, _ = _build_fixture(quantities=[5.0] * 3, store_available=100.0)  # too little history
    result = _orchestrator(service).analyze_inventory_vs_forecast(sku=sku)
    assert result["forecast"]["sufficient_data"] is False
    assert result["demand_gap"] is None
    assert result["requires_investigation"] is True
    assert any("insufficient history" in w for w in result["data_quality_warnings"])


# --------------------------------------------------------------------- #
# 5/6. Zero inventory / forecast exceeding inventory
# --------------------------------------------------------------------- #
def test_zero_inventory_with_forecast_demand():
    service, sku, _ = _build_fixture(quantities=[10.0] * 30, store_available=0.0)
    result = _orchestrator(service).analyze_inventory_vs_forecast(sku=sku)
    assert result["inventory"]["current_available"] == 0.0
    assert result["demand_gap"] == pytest.approx(70.0)
    assert result["requires_investigation"] is True


# --------------------------------------------------------------------- #
# 7. Inventory exceeding forecast demand
# --------------------------------------------------------------------- #
def test_inventory_exceeds_forecast_demand_no_investigation_needed():
    service, sku, _ = _build_fixture(quantities=[1.0] * 30, store_available=1000.0)
    result = _orchestrator(service).analyze_inventory_vs_forecast(sku=sku)
    assert result["demand_gap"] < 0
    assert result["requires_investigation"] is False


# --------------------------------------------------------------------- #
# 8. Mismatched SKU identifiers
# --------------------------------------------------------------------- #
class _WrongSkuInventoryEngine:
    def get_product_inventory_analysis(self, sku):
        return {
            "sku": "SKU-WRONG-0000",  # deliberately different from the requested sku
            "product_found": True,
            "product": {"product_name": "Mismatched Widget"},
            "observed": {
                "store_available_inventory": 10.0,
                "store_breakdown": [],
                "warehouse": {"warehouse_available": 0.0, "warehouse_inbound": 0.0, "by_warehouse": []},
            },
            "estimated": {"risk_level": "low"},
            "recommendation": {"suggested_replenishment_quantity": 0},
        }


def test_mismatched_sku_identifiers_are_flagged():
    service, sku, _ = _build_fixture(quantities=[10.0] * 30)
    orchestrator = RetailOrchestrationService(service=service, inventory_engine=_WrongSkuInventoryEngine())
    result = orchestrator.analyze_inventory_vs_forecast(sku=sku)
    assert result["sku_identifiers_matched"] is False
    assert result["requires_investigation"] is True
    assert any("mismatch" in w.lower() for w in result["data_quality_warnings"])


# --------------------------------------------------------------------- #
# 9. Missing inbound inventory (and timing-unclear inbound)
# --------------------------------------------------------------------- #
def test_no_inbound_stock_at_all():
    service, sku, _ = _build_fixture(quantities=[10.0] * 30, store_available=20.0, warehouse_inbound=0.0)
    result = _orchestrator(service).analyze_inventory_vs_forecast(sku=sku)
    assert result["inventory"]["known_inbound_stock_total"] == 0.0
    assert result["demand_gap_including_near_term_inbound"] == result["demand_gap"]


def test_inbound_stock_with_unclear_timing_is_excluded_from_gap():
    # Inbound exists but the supplier lead time (30 days) exceeds the 7-day horizon.
    service, sku, _ = _build_fixture(
        quantities=[10.0] * 30, store_available=20.0,
        warehouse_inbound=500.0, supplier_lead_time_days=30,
    )
    result = _orchestrator(service).analyze_inventory_vs_forecast(sku=sku, horizon_days=7)
    assert result["inventory"]["known_inbound_stock_total"] == 500.0
    assert result["inventory"]["inbound_expected_within_horizon"] == 0.0
    assert result["demand_gap_including_near_term_inbound"] is None
    assert any("unknown or" in w or "longer-than-horizon" in w for w in result["data_quality_warnings"])


def test_inbound_stock_with_clear_near_term_timing_is_included():
    service, sku, _ = _build_fixture(
        quantities=[10.0] * 30, store_available=20.0,
        warehouse_inbound=30.0, supplier_lead_time_days=3,
    )
    result = _orchestrator(service).analyze_inventory_vs_forecast(sku=sku, horizon_days=7)
    assert result["inventory"]["inbound_expected_within_horizon"] == 30.0
    assert result["demand_gap_including_near_term_inbound"] == pytest.approx(70.0 - (20.0 + 30.0))


# --------------------------------------------------------------------- #
# 10. API key unavailable
# --------------------------------------------------------------------- #
def test_answer_question_works_without_api_key(monkeypatch):
    # Note: "SKU-TEST-0001" is deliberately avoided here -- it contains the
    # substring "ST-000", which the shared STORE_PATTERN regex (same one
    # used by inventory_agent/demand_forecasting_agent's llm_explainer)
    # false-matches as a store ID. Pre-existing behavior, not fixed here.
    service, sku, _ = _build_fixture(sku="SKU-ABC-0001", quantities=[10.0] * 30)
    orchestrator = _orchestrator(service)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    result = answer_question(f"Should we investigate {sku}?", service=orchestrator)
    assert result["configured"] is False
    assert result["answer"] is None
    assert "analysis" in result["evidence"]
    assert "OPENAI_API_KEY" in result["message"]


# --------------------------------------------------------------------- #
# 11. Errors returned by either agent
# --------------------------------------------------------------------- #
class _AlwaysFailingInventoryEngine:
    def get_product_inventory_analysis(self, sku):
        raise RuntimeError("simulated inventory agent failure")


def test_single_sku_error_from_agent_propagates():
    service, sku, _ = _build_fixture()
    orchestrator = RetailOrchestrationService(service=service, inventory_engine=_AlwaysFailingInventoryEngine())
    with pytest.raises(RuntimeError):
        orchestrator.analyze_inventory_vs_forecast(sku=sku)


class _SelectivelyFailingInventoryEngine:
    def __init__(self, real_engine, fail_sku):
        self.real_engine = real_engine
        self.fail_sku = fail_sku

    def get_product_inventory_analysis(self, sku):
        if sku == self.fail_sku:
            raise RuntimeError(f"simulated failure for {sku}")
        return self.real_engine.get_product_inventory_analysis(sku)


def test_catalog_wide_scan_isolates_one_failing_sku():
    sku_good = "SKU-TEST-GOOD"
    sku_bad = "SKU-TEST-BAD"
    products = pd.DataFrame([
        {"sku": sku_good, "product_name": "Good", "category": "Home", "brand": "X", "selling_price": 10.0, "cost_price": 5.0},
        {"sku": sku_bad, "product_name": "Bad", "category": "Home", "brand": "X", "selling_price": 10.0, "cost_price": 5.0},
    ])
    stores = pd.DataFrame([{"store_id": "ST-001", "store_name": "A", "city": "X", "region": "Y", "store_type": "Flagship"}])
    sales = pd.concat([
        _daily_sales_rows(sku_good, "ST-001", "2026-09-01", [10.0] * 30),
        _daily_sales_rows(sku_bad, "ST-001", "2026-09-01", [10.0] * 30),
    ], ignore_index=True)
    service = FakeRetailDataService(products, stores, sales)
    real_inventory = InventoryRiskEngine(service=service)
    failing_inventory = _SelectivelyFailingInventoryEngine(real_inventory, fail_sku=sku_bad)
    orchestrator = RetailOrchestrationService(service=service, inventory_engine=failing_inventory)

    summary = orchestrator.analyze_inventory_vs_forecast()  # catalog-wide
    assert summary["total_products_analyzed"] == 2
    by_sku = {r["sku"]: r for r in summary["results"]}
    assert by_sku[sku_bad]["error"] is not None
    assert by_sku[sku_bad]["requires_investigation"] is True
    assert by_sku[sku_good]["error"] is None
    assert by_sku[sku_good]["forecast"]["sufficient_data"] is True


# --------------------------------------------------------------------- #
# Additional: catalog-wide scope, store scope, horizon validation,
# shared-service construction, and real end-to-end smoke test
# --------------------------------------------------------------------- #
def test_horizon_days_validation():
    service, sku, _ = _build_fixture()
    orchestrator = _orchestrator(service)
    with pytest.raises(ValueError):
        orchestrator.analyze_inventory_vs_forecast(sku=sku, horizon_days=0)


def test_unknown_store_id_raises():
    service, sku, _ = _build_fixture()
    orchestrator = _orchestrator(service)
    with pytest.raises(ValueError):
        orchestrator.analyze_inventory_vs_forecast(sku=sku, store_id="ST-999")


def test_store_scoped_analysis_matches_the_right_store_row():
    sku = "SKU-TEST-0001"
    products = pd.DataFrame([{"sku": sku, "product_name": "Multi Store Widget", "category": "Home", "brand": "X", "selling_price": 10.0, "cost_price": 5.0}])
    stores = pd.DataFrame([
        {"store_id": "ST-001", "store_name": "A", "city": "X", "region": "Y", "store_type": "Flagship"},
        {"store_id": "ST-002", "store_name": "B", "city": "X", "region": "Y", "store_type": "Flagship"},
    ])
    sales = pd.concat([
        _daily_sales_rows(sku, "ST-001", "2026-09-01", [10.0] * 30),
        _daily_sales_rows(sku, "ST-002", "2026-09-01", [2.0] * 30),
    ], ignore_index=True)
    inventory = pd.DataFrame([
        {"sku": sku, "location_id": "ST-001", "location_type": "store", "on_hand_quantity": 5.0, "reserved_quantity": 0, "available_quantity": 5.0, "last_updated": "2026-10-27"},
        {"sku": sku, "location_id": "ST-002", "location_type": "store", "on_hand_quantity": 500.0, "reserved_quantity": 0, "available_quantity": 500.0, "last_updated": "2026-10-27"},
    ])
    service = FakeRetailDataService(products, stores, sales, inventory)
    result = _orchestrator(service).analyze_inventory_vs_forecast(sku=sku, store_id="ST-001")
    assert result["inventory"]["current_available"] == 5.0  # ST-001's own row, not the 500 at ST-002


def test_catalog_wide_analysis_counts_products_requiring_investigation():
    sku_a = "SKU-TEST-000A"
    sku_b = "SKU-TEST-000B"
    products = pd.DataFrame([
        {"sku": sku_a, "product_name": "A", "category": "Home", "brand": "X", "selling_price": 10.0, "cost_price": 5.0},
        {"sku": sku_b, "product_name": "B", "category": "Home", "brand": "X", "selling_price": 10.0, "cost_price": 5.0},
    ])
    stores = pd.DataFrame([{"store_id": "ST-001", "store_name": "A", "city": "X", "region": "Y", "store_type": "Flagship"}])
    sales = pd.concat([
        _daily_sales_rows(sku_a, "ST-001", "2026-09-01", [10.0] * 30),
        _daily_sales_rows(sku_b, "ST-001", "2026-09-01", [10.0] * 30),
    ], ignore_index=True)
    inventory = pd.DataFrame([
        {"sku": sku_a, "location_id": "ST-001", "location_type": "store", "on_hand_quantity": 0.0, "reserved_quantity": 0, "available_quantity": 0.0, "last_updated": "2026-10-27"},
        {"sku": sku_b, "location_id": "ST-001", "location_type": "store", "on_hand_quantity": 1000.0, "reserved_quantity": 0, "available_quantity": 1000.0, "last_updated": "2026-10-27"},
    ])
    service = FakeRetailDataService(products, stores, sales, inventory)
    summary = _orchestrator(service).analyze_inventory_vs_forecast()
    assert summary["total_products_analyzed"] == 2
    assert summary["products_requiring_investigation"] == 1


def test_orchestrator_shares_one_service_instance_across_both_engines():
    service, _, _ = _build_fixture()
    orchestrator = RetailOrchestrationService(service=service)
    assert orchestrator.inventory_engine.service is service
    assert orchestrator.demand_engine.service is service


def test_default_orchestrator_runs_end_to_end_against_real_data():
    from orchestration.service import analyze_inventory_vs_forecast
    summary = analyze_inventory_vs_forecast()
    assert summary["total_products_analyzed"] > 0
