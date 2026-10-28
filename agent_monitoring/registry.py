"""
Static metadata for every implemented agent (plus the orchestrator) --
name, one-line purpose (summarized from that module's own docstring, not
invented), and the API path prefix used to attribute a logged HTTP
request to it. This is descriptive metadata only; it carries no execution
data itself -- see agent_monitoring/execution_log.py for that.
"""

AGENT_REGISTRY = [
    {
        "agent_key": "inventory",
        "agent_name": "Inventory Intelligence Agent",
        "purpose": (
            "Classifies stockout/excess risk per SKU from current store inventory and recent sales "
            "velocity, and suggests replenishment quantities capped by eligible warehouse stock."
        ),
        "path_prefix": "/inventory",
    },
    {
        "agent_key": "demand",
        "agent_name": "Demand Forecasting Agent",
        "purpose": (
            "Produces a weighted-moving-average demand forecast per SKU, detects demand spikes and "
            "declines, and backtests its own forecast error against held-out actuals."
        ),
        "path_prefix": "/demand",
    },
    {
        "agent_key": "promotion",
        "agent_name": "Promotion Intelligence Agent",
        "purpose": (
            "Assesses inventory readiness for upcoming/active promotions and compares promotional "
            "periods against historical baselines, never claiming a promotion caused a sales change."
        ),
        "path_prefix": "/promotions",
    },
    {
        "agent_key": "fulfillment",
        "agent_name": "Order Fulfillment Intelligence Agent",
        "purpose": (
            "Classifies order fulfillment risk from inventory readiness and the promised delivery "
            "date, and surfaces alternative fulfillment location candidates for at-risk orders."
        ),
        "path_prefix": "/fulfillment",
    },
    {
        "agent_key": "customer_experience",
        "agent_name": "Customer Experience Intelligence Agent",
        "purpose": (
            "Distinguishes confirmed delivery problems from predicted risk for at-risk orders and "
            "flags orders where human-reviewed service recovery may be warranted."
        ),
        "path_prefix": "/customer-experience",
    },
    {
        "agent_key": "orchestrator",
        "agent_name": "Retail Intelligence Orchestrator",
        "purpose": (
            "Routes natural-language business questions to the relevant agent(s) via deterministic "
            "keyword/ID matching and returns one structured, evidence-backed result."
        ),
        "path_prefix": "/retail-ai",
    },
]

AGENT_BY_KEY = {a["agent_key"]: a for a in AGENT_REGISTRY}


def agent_key_for_path(path):
    """Maps a request path (e.g. /api/v1/inventory/risks) to the agent_key
    whose path_prefix it starts with, or None if it doesn't belong to any
    monitored agent (health checks, dashboard aggregation, static assets,
    etc. are deliberately not attributed to any single agent)."""
    for agent in AGENT_REGISTRY:
        prefix = "/api/v1" + agent["path_prefix"]
        if path == prefix or path.startswith(prefix + "/"):
            return agent["agent_key"]
    return None
