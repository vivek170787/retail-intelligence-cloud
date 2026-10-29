"""
Natural-language question answering for the Inventory Intelligence Agent.

Flow (per project requirements -- the model never chooses tools itself):
  1. Python deterministically decides which risk_engine functions are
     relevant to the question (simple keyword/SKU/store-ID pattern
     matching -- not an LLM tool-call loop) and runs them to gather
     evidence.
  2. The question and evidence (as JSON) are sent to the OpenAI model,
     instructed to explain the evidence rather than invent new facts or
     do arithmetic of its own.

If OPENAI_API_KEY is not set, answer_question() still runs step 1 and
returns the gathered evidence with configured=False, so deterministic
behavior is never blocked on API configuration.
"""

import json
import re

from agent_feedback.store import get_active_adjustment
from inventory_agent.risk_engine import InventoryRiskEngine
from openai_config import get_openai_client, get_openai_model, is_configured

AGENT_KEY = "inventory"

_default_engine = InventoryRiskEngine()

_SKU_PATTERN = re.compile(r"SKU-[A-Z]{3}-\d{4}", re.IGNORECASE)
_STORE_PATTERN = re.compile(r"ST-\d{3}", re.IGNORECASE)

_REPLENISH_TERMS = ("replenish", "reorder", "restock", "need more", "need to order")
_TOP_RISK_TERMS = ("top", "worst", "biggest risk", "most at risk", "highest risk")

_BASE_SYSTEM_PROMPT = """\
You are an inventory intelligence assistant for an omnichannel retail \
platform. All data is synthetic test data generated for development.

You will be given a question and a JSON "evidence" object that was \
computed deterministically by Python business logic (not by you).

Rules:
- Answer using ONLY the evidence provided. Never invent SKUs, store IDs, \
quantities, dates, or recommendations that are not present in the evidence.
- Do not perform new arithmetic -- only reference numbers already present \
in the evidence; the Python layer already did the math.
- If the evidence needed to answer is missing, empty, or null, say so \
plainly rather than guessing.
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
    evidence = {"summary": engine.get_inventory_summary()}

    sku_match = _SKU_PATTERN.search(question)
    if sku_match:
        sku = sku_match.group(0).upper()
        evidence["product_analysis"] = engine.get_product_inventory_analysis(sku)
        evidence["warehouse_availability"] = engine.get_warehouse_availability(sku)

    store_match = _STORE_PATTERN.search(question)
    if store_match:
        evidence["store_inventory_risks"] = engine.get_store_inventory_risks(
            store_id=store_match.group(0).upper()
        )

    if any(term in q_lower for term in _REPLENISH_TERMS):
        evidence["replenishment_recommendations"] = engine.get_replenishment_recommendations()

    if any(term in q_lower for term in _TOP_RISK_TERMS):
        evidence["top_stockout_risks"] = engine.get_top_stockout_risks()

    if not sku_match and not store_match and "replenishment_recommendations" not in evidence \
            and "top_stockout_risks" not in evidence:
        evidence["inventory_risks"] = engine.get_inventory_risks()

    return evidence


def answer_question(question, engine=None):
    """Answer a natural-language inventory question.

    Returns a dict with keys: configured, question, evidence, answer,
    message. `answer` is populated only when OPENAI_API_KEY is set and the
    call succeeds; `message` explains what happened otherwise. The API key
    itself is never included in the return value.
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
