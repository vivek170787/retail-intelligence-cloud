"""
Static, hardcoded evaluation test cases for the Agent Evaluation workspace --
one list per agent_key, in the same "descriptive static metadata" style as
agent_monitoring/registry.py's AGENT_REGISTRY. Adding more cases is a code
change, not a UI action, matching that existing project convention.

Every question below is deliberately catalog-wide (no specific SKU/order
ID), so a test case's expected evidence does not depend on which synthetic
IDs happen to exist in this environment's generated dataset -- it only
depends on each agent's own deterministic keyword-routing logic in its
llm_explainer.py's _gather_evidence() (5 domain agents) or
orchestration/query_orchestrator.py's classify_query() (orchestrator).

Each test case is:
    {
        "id": unique string,
        "agent_key": one of agent_monitoring.registry.AGENT_REGISTRY's keys,
        "question": the natural-language question asked,
        "expected_evidence_keys": top-level keys (or "a.b.c" dot-paths) that
            must resolve to a non-missing, non-None value in the evidence
            dict gathered for that question,
        "answer_keywords_any": lower-cased substrings where at least one
            must appear in the natural-language answer (when one was
            generated) -- a lenient groundedness smell test, not a strict
            wording requirement.
    }
"""

TEST_CASES = [
    # -- inventory --------------------------------------------------------
    {
        "id": "inventory_top_risks",
        "agent_key": "inventory",
        "question": "What are the top stockout risks right now?",
        "expected_evidence_keys": ["summary", "top_stockout_risks"],
        "answer_keywords_any": ["risk", "stock"],
    },
    {
        "id": "inventory_replenishment",
        "agent_key": "inventory",
        "question": "Which products need replenishment?",
        "expected_evidence_keys": ["summary", "replenishment_recommendations"],
        "answer_keywords_any": ["replenish"],
    },
    # -- demand -------------------------------------------------------------
    {
        "id": "demand_top_forecasted",
        "agent_key": "demand",
        "question": "What are the top forecasted products?",
        "expected_evidence_keys": ["summary", "top_forecasted_products"],
        "answer_keywords_any": ["forecast", "demand"],
    },
    {
        "id": "demand_spikes",
        "agent_key": "demand",
        "question": "Are there any demand spikes I should know about?",
        "expected_evidence_keys": ["summary", "demand_spikes"],
        "answer_keywords_any": ["spike", "demand"],
    },
    # -- promotion ------------------------------------------------------------
    {
        "id": "promotion_stockout_risk",
        "agent_key": "promotion",
        "question": "Which promotions are at risk of stockout?",
        "expected_evidence_keys": ["promotion_stockout_risks", "promotions_with_inventory_risk"],
        "answer_keywords_any": ["stockout", "risk"],
    },
    {
        "id": "promotion_readiness",
        "agent_key": "promotion",
        "question": "Are upcoming promotions ready in terms of inventory readiness?",
        "expected_evidence_keys": ["readiness_report"],
        "answer_keywords_any": ["ready", "readiness", "inventory"],
    },
    # -- fulfillment ----------------------------------------------------------
    {
        "id": "fulfillment_due_today",
        "agent_key": "fulfillment",
        "question": "Which orders are due today?",
        "expected_evidence_keys": ["orders_due_today"],
        "answer_keywords_any": ["today", "order"],
    },
    {
        "id": "fulfillment_shortages",
        "agent_key": "fulfillment",
        "question": "Which orders have inventory shortages?",
        "expected_evidence_keys": ["orders_with_inventory_shortages"],
        "answer_keywords_any": ["shortage", "inventory"],
    },
    # -- customer_experience ------------------------------------------------
    {
        "id": "cx_recovery_recommendations",
        "agent_key": "customer_experience",
        "question": "What service recovery actions are recommended?",
        "expected_evidence_keys": ["service_recovery_recommendations"],
        "answer_keywords_any": ["recovery", "recommend"],
    },
    {
        "id": "cx_summary",
        "agent_key": "customer_experience",
        "question": "Give me a summary of customer experience risks.",
        "expected_evidence_keys": ["summary"],
        "answer_keywords_any": ["summary", "customer"],
    },
    # -- orchestrator ---------------------------------------------------------
    {
        "id": "orchestrator_executive_summary",
        "agent_key": "orchestrator",
        "question": "Give me an executive summary of the business.",
        "expected_evidence_keys": ["inventory", "demand", "promotion", "fulfillment", "customer_experience"],
        "answer_keywords_any": ["summary", "business", "inventory", "demand"],
    },
    {
        "id": "orchestrator_stockout_prevention",
        "agent_key": "orchestrator",
        "question": "Run a stockout prevention workflow for the catalog.",
        "expected_evidence_keys": ["top_stockout_risks", "replenishment_recommendations"],
        "answer_keywords_any": ["stockout", "inventory", "risk"],
    },
]

TEST_CASES_BY_AGENT = {}
for _case in TEST_CASES:
    TEST_CASES_BY_AGENT.setdefault(_case["agent_key"], []).append(_case)
