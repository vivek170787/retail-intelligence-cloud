"""
Natural-language question answering for the Demand Forecasting Agent.

Mirrors inventory_agent/llm_explainer.py's flow: Python deterministically
decides which forecasting_engine functions are relevant to a question
(keyword/SKU/store-ID pattern matching, not an LLM tool-call loop), runs
them to gather evidence, then asks the OpenAI model to explain that
evidence -- never to invent SKUs, historical sales, forecast values, or
inventory quantities, and never to do its own arithmetic.

Reuses the project's shared OpenAI client/config (openai_config.py) rather
than constructing a separate client. If OPENAI_API_KEY is not set,
answer_question() still gathers and returns the deterministic evidence.
"""

import json
import re

from demand_forecasting_agent.forecasting_engine import DemandForecastEngine
from openai_config import get_openai_client, get_openai_model, is_configured

_default_engine = DemandForecastEngine()

_SKU_PATTERN = re.compile(r"SKU-[A-Z]{3}-\d{4}", re.IGNORECASE)
_STORE_PATTERN = re.compile(r"ST-\d{3}", re.IGNORECASE)

_SPIKE_TERMS = ("spike", "surge", "jump", "unusual increase")
_DECLINE_TERMS = ("declin", "drop", "falling", "slowdown", "decreas")
_TOP_TERMS = ("top", "highest", "most demand", "biggest demand")
_INVESTIGATE_TERMS = ("investigate", "planner", "priorit", "focus on", "look into")

SYSTEM_PROMPT = """\
You are a demand forecasting assistant for an omnichannel retail platform. \
All data is synthetic test data generated for development.

You will be given a question and a JSON "evidence" object computed \
deterministically by Python statistical functions (not by you).

Rules:
- Answer using ONLY the evidence provided. Never invent SKUs, historical \
sales figures, forecast numbers, or inventory quantities that are not \
present in the evidence.
- The forecast is a simple statistical baseline (a weighted moving \
average, sometimes compared against a day-of-week seasonal average) -- \
NOT a guaranteed prediction. Do not describe it as certain, and do not \
state an uncalibrated number as a statistically reliable confidence \
interval unless the evidence explicitly provides one.
- Do not perform new arithmetic -- only reference numbers already present \
in the evidence.
- If a demand gap or replenishment figure is present, make clear it is an \
estimate for investigation, not a final replenishment decision or an \
automatic action.
- If the evidence needed to answer is missing, empty, or flagged \
insufficient_data/insufficient_history, say so plainly rather than guessing.
- Keep the answer concise: a few sentences, plus a short list if helpful.
"""


def _gather_evidence(question, engine):
    q_lower = question.lower()
    evidence = {"summary": engine.get_demand_summary()}

    sku_match = _SKU_PATTERN.search(question)
    if sku_match:
        sku = sku_match.group(0).upper()
        evidence["forecast"] = engine.forecast_demand(sku)
        evidence["inventory_comparison"] = engine.compare_forecast_with_inventory(sku)

    store_match = _STORE_PATTERN.search(question)
    if store_match and sku_match:
        evidence["store_forecast"] = engine.forecast_demand(
            sku_match.group(0).upper(), store_id=store_match.group(0).upper()
        )

    if any(term in q_lower for term in _SPIKE_TERMS):
        evidence["demand_spikes"] = engine.detect_demand_spikes()

    if any(term in q_lower for term in _DECLINE_TERMS):
        evidence["declining_demand"] = engine.detect_declining_demand()

    if any(term in q_lower for term in _TOP_TERMS):
        evidence["top_forecasted_products"] = engine.get_top_forecasted_products()

    if any(term in q_lower for term in _INVESTIGATE_TERMS):
        evidence.setdefault("demand_spikes", engine.detect_demand_spikes())
        evidence.setdefault("declining_demand", engine.detect_declining_demand())
        evidence.setdefault("top_forecasted_products", engine.get_top_forecasted_products(limit=5))

    return evidence


def answer_question(question, engine=None):
    """Answer a natural-language demand forecasting question.

    Returns a dict with keys: configured, question, evidence, answer,
    message. `answer` is populated only when an OpenAI API key is
    configured and the call succeeds. The API key itself is never
    included in the return value.
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
                "directly from the data. Copy .env.example to .env and set a "
                "real OPENAI_API_KEY (and optionally OPENAI_MODEL) to enable "
                "natural-language answers."
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
