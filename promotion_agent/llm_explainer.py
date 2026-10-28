"""
Natural-language question answering for the Promotion Intelligence Agent.

Same flow as inventory_agent/llm_explainer.py and demand_forecasting_agent/
llm_explainer.py: Python deterministically decides which promotion_engine
functions are relevant (SKU pattern + keyword matching, not an LLM
tool-call loop), runs them directly, then -- only if an OpenAI API key is
configured -- asks the model to explain the already-computed evidence.
The model never computes uplift, inventory, or forecast numbers itself.

Reuses the shared openai_config.py client. Works fully without an API key:
answer_question() still gathers and returns the deterministic evidence.
"""

import json
import re

from promotion_agent.promotion_engine import PromotionIntelligenceEngine
from openai_config import get_openai_client, get_openai_model, is_configured

_default_engine = PromotionIntelligenceEngine()

_SKU_PATTERN = re.compile(r"SKU-[A-Z]{3}-\d{4}", re.IGNORECASE)

_RISK_TERMS = ("risk", "stockout", "shortage", "insufficient")
_READINESS_TERMS = ("sufficient", "ready", "readiness", "prepared")
_HISTORY_TERMS = ("differ", "history", "historical", "compare", "uplift", "did sales")
_PLANNER_TERMS = ("planner", "attention", "investigate", "priorit")

SYSTEM_PROMPT = """\
You are a promotion planning assistant for an omnichannel retail platform. \
All data is synthetic test data generated for development.

You will be given a question and a JSON "evidence" object computed \
deterministically by Python (promotion schedules, historical sales \
comparisons, baseline demand forecasts from the Demand Forecasting Agent, \
and current inventory from the Inventory Intelligence Agent). You did not \
compute any of these numbers.

Rules:
- Explain the evidence; do not recompute or adjust any number in it. \
Never invent SKUs, discount percentages, uplift percentages, inventory \
quantities, or forecast values not present in the evidence.
- If a historical comparison has comparable: false, say plainly that an \
uplift could not be reliably estimated for that promotion -- do not guess \
a percentage anyway.
- If promotional_demand_estimate.source is "unknown", say the promotional \
uplift is unknown and only the baseline forecast was used -- never assume \
a specific increase.
- If source is "assumed_scenario", make clear that figure is a what-if \
assumption supplied by the user, not an observed or guaranteed outcome.
- All recommendations in the evidence are for human review only. Never \
phrase your answer as if a promotion, order, price change, or inventory \
transfer has already happened or will happen automatically.
- If the evidence needed to answer is missing or empty, say so plainly.
- Keep the answer concise: a few sentences, plus a short list if helpful.
"""


def _gather_evidence(question, engine):
    q_lower = question.lower()
    sku_match = _SKU_PATTERN.search(question)
    evidence = {}

    if sku_match:
        sku = sku_match.group(0).upper()
        evidence["sku_analysis"] = engine.analyze_promotion_for_sku(sku)
        if any(term in q_lower for term in _HISTORY_TERMS):
            evidence["historical_comparison"] = engine.compare_promotional_and_nonpromotional_sales(sku=sku)
        return evidence

    if any(term in q_lower for term in _RISK_TERMS):
        evidence["promotion_stockout_risks"] = engine.get_promotion_stockout_risks()
        evidence["promotions_with_inventory_risk"] = engine.get_promotions_with_inventory_risk()
    if any(term in q_lower for term in _READINESS_TERMS):
        evidence["readiness_report"] = engine.get_promotion_readiness_report()
    if any(term in q_lower for term in _HISTORY_TERMS):
        evidence["historical_comparison"] = engine.compare_promotional_and_nonpromotional_sales()
    if any(term in q_lower for term in _PLANNER_TERMS):
        evidence.setdefault("promotion_stockout_risks", engine.get_promotion_stockout_risks())
        evidence.setdefault("promotions_with_inventory_risk", engine.get_promotions_with_inventory_risk())

    if not evidence:
        evidence["upcoming_promotions"] = engine.get_upcoming_promotions()
        evidence["summary"] = engine.get_promotional_demand_summary()

    return evidence


def answer_question(question, engine=None):
    """Answer a natural-language promotion question.

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
