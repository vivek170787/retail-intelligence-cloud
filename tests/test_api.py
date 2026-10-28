"""
Tests for the FastAPI backend (api/). Uses FastAPI's TestClient against the
real app -- no mocking of the orchestrator or engines -- and asserts each
route is a pure proxy (same data as calling the underlying engine directly),
never a recalculation.
"""

from fastapi.encoders import jsonable_encoder
from fastapi.testclient import TestClient

from api.main import app
from api.dependencies import get_orchestrator

client = TestClient(app)
orchestrator = get_orchestrator()


def as_json(value):
    """Round-trips a raw engine result (which may contain pandas Timestamps,
    numpy scalars, etc.) through the same encoder FastAPI itself uses for
    responses, so comparisons are apples-to-apples with resp.json()."""
    return jsonable_encoder(value)


def test_health():
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_dashboard_summary_matches_command_center_builder():
    from dashboard.data_prep import build_command_center

    resp = client.get("/api/v1/dashboard/summary")
    assert resp.status_code == 200
    expected = build_command_center(orchestrator, days_ahead=7)
    assert resp.json() == as_json(expected)


def test_dashboard_sales_trend_matches_catalog_builder():
    from dashboard.data_prep import build_catalog_sales_history_series

    resp = client.get("/api/v1/dashboard/sales-trend")
    assert resp.status_code == 200
    body = resp.json()
    assert body["error"] is None
    assert len(body["dates"]) == len(body["values"])
    assert len(body["dates"]) > 0

    series, error = build_catalog_sales_history_series(orchestrator)
    assert error is None
    assert body["values"] == [float(v) for v in series.values]


def test_inventory_risks_is_pure_proxy():
    resp = client.get("/api/v1/inventory/risks")
    assert resp.status_code == 200
    assert resp.json() == as_json(orchestrator.svc.inventory_engine.get_inventory_risks())


def test_inventory_summary():
    resp = client.get("/api/v1/inventory/summary")
    assert resp.status_code == 200
    assert resp.json() == as_json(orchestrator.svc.inventory_engine.get_inventory_summary())


def test_inventory_top_stockout_risks_limit_param():
    resp = client.get("/api/v1/inventory/top-stockout-risks", params={"limit": 3})
    assert resp.status_code == 200
    body = resp.json()
    assert body == as_json(orchestrator.svc.inventory_engine.get_top_stockout_risks(limit=3))
    assert len(body) <= 3


def test_inventory_replenishment():
    resp = client.get("/api/v1/inventory/replenishment")
    assert resp.status_code == 200
    assert resp.json() == as_json(orchestrator.svc.inventory_engine.get_replenishment_recommendations())


def test_product_inventory_analysis_for_real_sku():
    risks = orchestrator.svc.inventory_engine.get_inventory_risks()
    sku = risks[0]["sku"]
    resp = client.get(f"/api/v1/inventory/{sku}")
    assert resp.status_code == 200
    assert resp.json() == as_json(orchestrator.svc.inventory_engine.get_product_inventory_analysis(sku))


def test_inventory_analysis_empty_sku_returns_400():
    resp = client.get("/api/v1/inventory/%20")
    assert resp.status_code == 400
    body = resp.json()
    assert "error" in body
    assert body["error"]["type"] == "invalid_request"


def test_unknown_route_returns_consistent_error_envelope_not_default_404():
    resp = client.get("/api/v1/this-route-does-not-exist")
    assert resp.status_code == 404
    assert resp.json() == {
        "error": {"message": "The requested resource was not found.", "type": "not_found"}
    }


def test_disallowed_method_returns_consistent_error_envelope():
    resp = client.post("/api/v1/health")
    assert resp.status_code == 405
    assert resp.json()["error"]["type"] == "method_not_allowed"


def test_malformed_query_param_returns_consistent_error_envelope():
    resp = client.get("/api/v1/inventory/top-stockout-risks", params={"limit": "not-a-number"})
    assert resp.status_code == 422
    body = resp.json()
    assert body["error"]["type"] == "validation_error"
    assert "limit" in body["error"]["message"]


def test_malformed_request_body_returns_consistent_error_envelope():
    resp = client.post("/api/v1/retail-ai/query", json={"not_query": "oops"})
    assert resp.status_code == 422
    assert resp.json()["error"]["type"] == "validation_error"


def test_cors_allows_the_local_frontend_origin():
    resp = client.get("/api/v1/health", headers={"Origin": "http://localhost:3000"})
    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_demand_top_forecasted():
    resp = client.get("/api/v1/demand/top-forecasted", params={"horizon_days": 7, "limit": 5})
    assert resp.status_code == 200
    assert resp.json() == as_json(orchestrator.svc.demand_engine.get_top_forecasted_products(horizon_days=7, limit=5))


def test_demand_forecast_for_real_sku():
    risks = orchestrator.svc.inventory_engine.get_inventory_risks()
    sku = risks[0]["sku"]
    resp = client.get(f"/api/v1/demand/{sku}/forecast", params={"horizon_days": 7})
    assert resp.status_code == 200
    assert resp.json() == as_json(orchestrator.svc.demand_engine.forecast_demand(sku, horizon_days=7, store_id=None))


def test_demand_sales_history_matches_builder():
    from dashboard.data_prep import build_sales_history_series

    risks = orchestrator.svc.inventory_engine.get_inventory_risks()
    sku = risks[0]["sku"]
    resp = client.get(f"/api/v1/demand/{sku}/sales-history")
    assert resp.status_code == 200
    body = resp.json()
    assert body["error"] is None
    assert len(body["dates"]) == len(body["values"])

    series, error = build_sales_history_series(orchestrator, sku)
    assert error is None
    assert body["values"] == [float(v) for v in series.values]


def test_demand_compare_inventory_for_real_sku():
    risks = orchestrator.svc.inventory_engine.get_inventory_risks()
    sku = risks[0]["sku"]
    resp = client.get(f"/api/v1/demand/{sku}/compare-inventory", params={"horizon_days": 7})
    assert resp.status_code == 200
    assert resp.json() == as_json(
        orchestrator.svc.demand_engine.compare_forecast_with_inventory(sku, horizon_days=7)
    )


def test_promotions_upcoming():
    resp = client.get("/api/v1/promotions/upcoming", params={"days_ahead": 14})
    assert resp.status_code == 200
    assert resp.json() == as_json(orchestrator.svc.promotion_engine.get_upcoming_promotions(days_ahead=14))


def test_promotions_readiness_report():
    resp = client.get("/api/v1/promotions/readiness")
    assert resp.status_code == 200
    assert resp.json() == as_json(orchestrator.svc.promotion_engine.get_promotion_readiness_report(days_ahead=None))


def test_fulfillment_at_risk():
    resp = client.get("/api/v1/fulfillment/at-risk")
    assert resp.status_code == 200
    assert resp.json() == as_json(orchestrator.svc.fulfillment_engine.get_orders_at_risk())


def test_fulfillment_order_not_found_is_200_with_order_found_false():
    resp = client.get("/api/v1/fulfillment/orders/ORD-999999")
    assert resp.status_code == 200
    body = resp.json()
    assert body["order_found"] is False


def test_customer_experience_impact_risks():
    resp = client.get("/api/v1/customer-experience/impact-risks")
    assert resp.status_code == 200
    assert resp.json() == as_json(orchestrator.svc.cx_engine.get_customer_impact_risks())


def test_retail_ai_query_executive_summary():
    resp = client.post("/api/v1/retail-ai/query", json={"query": "Give me today's retail risk summary."})
    assert resp.status_code == 200
    body = resp.json()
    assert body["category"] == "cross_agent_retail_analysis"
    assert "severity" in body
    assert "disclaimer" in body


def test_retail_ai_query_empty_string_returns_400():
    resp = client.post("/api/v1/retail-ai/query", json={"query": "   "})
    assert resp.status_code == 400
    assert resp.json()["error"]["type"] == "invalid_request"


def test_no_openai_key_required_for_retail_ai_query(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    resp = client.post("/api/v1/retail-ai/query", json={"query": "Which stores are at risk of stockouts?"})
    assert resp.status_code == 200


def test_retail_ai_query_always_includes_ai_narration_field():
    resp = client.post("/api/v1/retail-ai/query", json={"query": "Which products need replenishment?"})
    assert resp.status_code == 200
    narration = resp.json()["ai_narration"]
    assert set(narration) == {"configured", "answer", "message"}


def test_retail_ai_status_reports_a_boolean_never_the_key():
    resp = client.get("/api/v1/retail-ai/status")
    assert resp.status_code == 200
    body = resp.json()
    assert list(body) == ["openai_narration_configured"]
    assert isinstance(body["openai_narration_configured"], bool)


def test_agent_monitoring_agents_lists_every_registered_agent():
    from agent_monitoring.registry import AGENT_REGISTRY

    resp = client.get("/api/v1/agent-monitoring/agents")
    assert resp.status_code == 200
    body = resp.json()
    assert {a["agent_key"] for a in body} == {a["agent_key"] for a in AGENT_REGISTRY}
    for agent in body:
        assert agent["status"] in ("healthy", "error", "no_executions_recorded")
        assert agent["total_runs"] == agent["successful_runs"] + agent["failed_runs"]


def test_agent_monitoring_executions_for_known_agent():
    resp = client.get("/api/v1/agent-monitoring/agents/inventory/executions", params={"limit": 5})
    assert resp.status_code == 200
    assert len(resp.json()) <= 5


def test_agent_monitoring_executions_unknown_agent_returns_400():
    resp = client.get("/api/v1/agent-monitoring/agents/not_a_real_agent/executions")
    assert resp.status_code == 400
    assert resp.json()["error"]["type"] == "invalid_request"


def test_agent_monitoring_combined_executions_feed():
    resp = client.get("/api/v1/agent-monitoring/executions", params={"limit": 10})
    assert resp.status_code == 200
    assert len(resp.json()) <= 10


def test_data_quality_report_is_pure_proxy():
    from data_quality.report import build_quality_report

    resp = client.get("/api/v1/data-quality/report")
    assert resp.status_code == 200
    assert resp.json() == as_json(build_quality_report(service=orchestrator.svc.service))


def test_data_sources_overview_is_pure_proxy():
    from data_sources.registry import get_data_sources_overview

    resp = client.get("/api/v1/data-sources/overview")
    assert resp.status_code == 200
    assert resp.json() == as_json(get_data_sources_overview(service=orchestrator.svc.service))


def test_data_sources_overview_never_claims_a_live_external_integration():
    resp = client.get("/api/v1/data-sources/overview")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["connectors"]) > 0
    assert all(c["integration_type"] == "local_csv_file" for c in body["connectors"])
