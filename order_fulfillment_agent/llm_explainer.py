"""
Natural-language question answering for the Order Fulfillment Intelligence
Agent. Same flow as every other agent's llm_explainer.py: Python
deterministically decides which fulfillment_engine functions are relevant
(order-ID/keyword matching, not an LLM tool-call loop), runs them directly,
then -- only if an OpenAI API key is configured -- asks the model to
explain the already-computed evidence. The model never invents order
statuses, tracking events, delivery dates, or inventory figures.

Reuses the shared openai_config.py client. Works fully without an API key.
"""

import json
import re

from order_fulfillment_agent.fulfillment_engine import OrderFulfillmentEngine
from openai_config import get_openai_client, get_openai_model, is_configured

_default_engine = OrderFulfillmentEngine()

_ORDER_ID_PATTERN = re.compile(r"ORD-\d{6}", re.IGNORECASE)

_SHORTAGE_TERMS = ("inventory", "shortage", "stock", "insufficient")
_ALTERNATIVE_TERMS = ("another store", "alternative", "other warehouse", "reassign", "transfer")
_TODAY_TERMS = ("today", "due today", "need attention")
_READY_TERMS = ("ready", "uncertain delivery", "feasib")

SYSTEM_PROMPT = """\
You are an order fulfillment assistant for an omnichannel retail platform. \
All data is synthetic test data generated for development.

You will be given a question and a JSON "evidence" object computed \
deterministically by Python (order details, inventory readiness from the \
Inventory Intelligence Agent, and -- only when relevant -- baseline demand \
or promotion context). You did not compute any of these numbers.

Rules:
- Explain the evidence; do not recompute or adjust any number in it. \
Never invent order statuses, tracking events, carrier information, actual \
delivery dates, or inventory quantities not present in the evidence.
- delivery_feasibility.status is always "unknown" in this dataset -- there \
is no transit-time or tracking data. Never claim an order will or won't \
arrive on time beyond what inventory_readiness and promised_date_passed \
already show.
- An order with a future promised date and sufficient inventory is healthy \
-- never describe it as at risk merely because it hasn't shipped yet.
- Alternative fulfillment candidates are always "candidate_requires_validation" \
or "insufficient_stock" -- never describe one as a confirmed, ready-to-use \
solution, and never imply inventory has been or will be transferred.
- All recommendations are for human review only -- never phrase your answer \
as if an order, transfer, or notification has already happened.
- If the evidence is missing or empty (e.g. unknown order_id), say so plainly.
- Keep the answer concise: a few sentences, plus a short list if helpful.
"""


def _gather_evidence(question, engine):
    q_lower = question.lower()
    order_match = _ORDER_ID_PATTERN.search(question)
    evidence = {}

    if order_match:
        order_id = order_match.group(0).upper()
        evidence["order_analysis"] = engine.analyze_order_fulfillment(order_id)
        if any(term in q_lower for term in _ALTERNATIVE_TERMS):
            evidence["alternative_options"] = engine.find_alternative_fulfillment_options(order_id)
        return evidence

    if any(term in q_lower for term in _TODAY_TERMS):
        evidence["orders_due_today"] = engine.get_orders_due_today()
    if any(term in q_lower for term in _SHORTAGE_TERMS):
        evidence["orders_with_inventory_shortages"] = engine.get_orders_with_inventory_shortages()
    if any(term in q_lower for term in _READY_TERMS):
        evidence.setdefault("orders_with_inventory_shortages", engine.get_orders_with_inventory_shortages())
        evidence.setdefault("orders_at_risk", engine.get_orders_at_risk())

    if not evidence:
        evidence["orders_at_risk"] = engine.get_orders_at_risk()
        evidence["summary"] = engine.get_fulfillment_risk_summary()

    return evidence


def answer_question(question, engine=None):
    """Answer a natural-language order fulfillment question.

    Returns a dict with keys: configured, question, evidence, answer,
    message. The API key itself is never included in the return value.
    """
    engine = engine or _default_engine
    evidence = _gather_evidence(question, engine)

    if not is_configured():
        return {
            "configured": False,
            "question": question,
            "evidence": evidence,
            "answer": None,
            "message": (
                "OPENAI_API_KEY is not set, so no natural-language explanation "
                "was generated. The deterministic evidence below was computed "
                "directly from the data via direct Python calls. Copy "
                ".env.example to .env and set a real OPENAI_API_KEY (and "
                "optionally OPENAI_MODEL) to enable natural-language answers."
            ),
        }

    client = get_openai_client()
    model = get_openai_model()

    response = client.chat.completions.create(
        model=model,
        temperature=0,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Question: {question}\n\nEvidence (JSON):\n{json.dumps(evidence, indent=2, default=str)}",
            },
        ],
    )

    return {
        "configured": True,
        "question": question,
        "evidence": evidence,
        "answer": response.choices[0].message.content,
        "message": None,
    }
