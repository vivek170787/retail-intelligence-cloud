"""
Agent definition for the retail data assistant.

Model: "gpt-5.6-luna" -- confirmed via `agents.models.get_default_model()`
to be this installed openai-agents==0.22.3 SDK's own built-in default model,
and confirmed via `openai.types.shared.chat_model.ChatModel` to be a live,
non-deprecated model (not scheduled for shutdown). Chosen as the
cheapest/fastest general-purpose tier appropriate for straightforward
tool-calling lookups like this agent's -- unlike the reasoning-tier models
documented elsewhere (e.g. "gpt-6.1-sol"), it needs no explicit
ModelSettings(reasoning=...) tuning. Override by editing MODEL below, or by
setting the OPENAI_DEFAULT_MODEL env var and passing model=None instead.
"""

from agents import Agent

from retail_agent.tools import (
    get_products,
    get_stores,
    get_sales,
    get_sales_by_sku,
    get_inventory,
    get_inventory_by_sku,
    get_warehouse_stock,
    get_orders,
    get_orders_by_status,
    get_orders_by_sku,
    get_marketplace_listings,
    get_promotions,
)

MODEL = "gpt-5.6-luna"

INSTRUCTIONS = """\
You are a retail operations assistant for an omnichannel retail platform.
You answer questions about products, stores, POS sales, inventory,
warehouse stock, orders, marketplace listings, and promotions using ONLY
the data returned by your tools. All data is synthetic test data generated
for development -- never invent, estimate, or supplement it with outside
knowledge about real products, stores, or companies.

Guidelines:
- Always call the appropriate tool to look up data; never answer from
  memory or assumption.
- An empty list result means "no matching records found" -- this is a
  normal, valid outcome (e.g. a real SKU with no current promotions), not
  an error. Say so plainly rather than treating it as a failure.
- If a tool returns a string starting with "Invalid input" instead of a
  list, relay the problem to the user in plain language and ask for a
  corrected input (e.g. a non-empty SKU or status); do not retry blindly.
- The get_sales, get_inventory, and get_orders tools return a bounded
  sample (total_rows vs returned_rows) since those datasets can be large.
  If returned_rows is less than total_rows, mention that you are showing a
  partial sample, not the complete dataset.
- When asked for data not covered by any tool, say so rather than guessing.
- Keep answers concise and grounded in the specific records returned.
"""

retail_agent = Agent(
    name="Retail Data Assistant",
    instructions=INSTRUCTIONS,
    model=MODEL,
    tools=[
        get_products,
        get_stores,
        get_sales,
        get_sales_by_sku,
        get_inventory,
        get_inventory_by_sku,
        get_warehouse_stock,
        get_orders,
        get_orders_by_status,
        get_orders_by_sku,
        get_marketplace_listings,
        get_promotions,
    ],
)
