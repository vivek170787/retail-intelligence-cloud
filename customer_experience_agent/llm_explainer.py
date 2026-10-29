"""
Natural-language question answering for the Customer Experience
Intelligence Agent. Same flow as every other agent's llm_explainer.py:
Python deterministically gathers evidence via cx_engine functions, then --
only if an OpenAI API key is configured -- asks the model to explain it.
The model never invents order statuses, delivery dates, tracking events,
or inventory figures, and never proposes an action beyond what the
evidence already recommends.

Reuses the shared openai_config.py client. Works fully without an API key.
"""

import json
import re

from agent_feedback.store import get_active_adjustment
from customer_experience_agent.cx_engine import CustomerExperienceEngine
from openai_config import get_openai_client, get_openai_model, is_configured

AGENT_KEY = "customer_experience"

_default_engine = CustomerExperienceEngine()

_ORDER_ID_PATTERN = re.compile(r"ORD-\d{6}", re.IGNORECASE)

_RECOVERY_TERMS = ("recovery", "recommend", "action")
_SUMMARY_TERMS = ("summary", "overview", "how many")

_BASE_SYSTEM_PROMPT = """\
You are a customer experience assistant for an omnichannel retail \
platform. All data is synthetic test data generated for development.

You will be given a question and a JSON "evidence" object computed \
deterministically by Python (order and fulfillment facts from the Order \
Fulfillment and Inventory Intelligence Agents, plus marketplace \
availability context). You did not compute any of these numbers.

Rules:
- Explain the evidence; do not recompute or adjust any value in it. Never \
invent order statuses, tracking events, delivery dates, customer \
preferences, or inventory/marketplace figures not present in the evidence.
- "problem_type": "confirmed" means the promised date has already passed \
(a fact); "predicted" means inventory is short but the date hasn't passed \
yet (a forward-looking risk, not a certainty). Never blur this distinction.
- alternative_product_recommendation.available is always false in this \
dataset -- never suggest a specific alternative product anyway.
- human_reviewed_recovery_action never names a specific action (no \
discount, refund, or compensation amount) -- only that human review may \
be warranted. Never state a specific recovery action as if it were policy.
- potential_cancellation_risk is a conservative flag for human review, \
never a prediction that the order will be cancelled.
- All recommended_actions are for human review only -- never phrase your \
answer as if an order, transfer, or customer message has already happened \
or will happen automatically.
- If the evidence is missing or empty (e.g. unknown order_id), say so plainly.
- Keep the answer concise: a few sentences, plus a short list if helpful.
"""


def _system_prompt():
    """_BASE_SYSTEM_PROMPT, plus the most recent AI-feedback-loop prompt
    adjustment for this agent (agent_feedback/retuning.py), if one has
    been triggered by accumulated negative user feedback."""
    adjustment = get_active_adjustment(AGENT_KEY)
    if not adjustment:
        return _BASE_SYSTEM_PROMPT
    return f"{_BASE_SYSTEM_PROMPT}\n{adjustment}\n"


def _gather_evidence(question, engine):
    q_lower = question.lower()
    order_match = _ORDER_ID_PATTERN.search(question)

    if order_match:
        return {"order_experience": engine.analyze_customer_order_experience(order_match.group(0).upper())}

    if any(term in q_lower for term in _RECOVERY_TERMS):
        return {"service_recovery_recommendations": engine.get_service_recovery_recommendations()}

    if any(term in q_lower for term in _SUMMARY_TERMS):
        return {"summary": engine.get_customer_experience_summary()}

    return {
        "customer_impact_risks": engine.get_customer_impact_risks(),
        "summary": engine.get_customer_experience_summary(),
    }


def answer_question(question, engine=None):
    """Answer a natural-language customer-experience question.

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

    try:
        client = get_openai_client()
        model = get_openai_model()
        response = client.chat.completions.create(
            model=model,
            temperature=0,
            messages=[
                {"role": "system", "content": _system_prompt()},
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
    except Exception as exc:
        return {
            "configured": True,
            "question": question,
            "evidence": evidence,
            "answer": None,
            "message": f"Natural-language explanation failed ({type(exc).__name__}); showing the deterministic evidence only.",
        }
