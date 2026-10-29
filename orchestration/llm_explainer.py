"""
Natural-language question answering for the combined orchestration service.

Mirrors inventory_agent/llm_explainer.py and demand_forecasting_agent/
llm_explainer.py's flow exactly: Python deterministically decides which
analyze_inventory_vs_forecast() call is relevant to a question (SKU/store-ID
pattern matching, not an LLM tool-call loop), runs it directly, then -- only
if an OpenAI API key is configured -- asks the model to explain that
evidence. The model never performs the comparison itself and never invents
quantities; it only narrates numbers already computed in Python.

Reuses the project's shared OpenAI client/config (openai_config.py).
answer_question() works fully without an API key -- it still returns the
deterministic evidence, per requirement 8.
"""

import json
import re

from agent_feedback.store import get_active_adjustment
from orchestration.service import RetailOrchestrationService
from openai_config import get_openai_client, get_openai_model, is_configured

AGENT_KEY = "orchestrator"

_default_service = RetailOrchestrationService()

_SKU_PATTERN = re.compile(r"SKU-[A-Z]{3}-\d{4}", re.IGNORECASE)
_STORE_PATTERN = re.compile(r"ST-\d{3}", re.IGNORECASE)

_BASE_SYSTEM_PROMPT = """\
You are a supply-planning assistant for an omnichannel retail platform, \
explaining a combined inventory-vs-forecast comparison. All data is \
synthetic test data generated for development.

You will be given a question and a JSON "evidence" object computed \
deterministically by Python (forecast demand from the Demand Forecasting \
Agent, current inventory from the Inventory Intelligence Agent, and a gap \
calculated by comparing them). You did not compute any of these numbers.

Rules:
- Explain the evidence; do not recompute, adjust, or second-guess any \
number in it. Never invent SKUs, quantities, store IDs, or figures not \
present in the evidence.
- demand_gap and demand_gap_including_near_term_inbound are preliminary \
estimates for investigation only -- never describe them as a final \
replenishment decision or an action already taken.
- If a field is null (e.g. forecast unavailable, inbound timing unclear), \
say so plainly instead of guessing a value.
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


def _gather_evidence(question, service):
    q_lower = question.lower()
    sku_match = _SKU_PATTERN.search(question)
    store_match = _STORE_PATTERN.search(question)

    sku = sku_match.group(0).upper() if sku_match else None
    store_id = store_match.group(0).upper() if store_match else None

    analysis = service.analyze_inventory_vs_forecast(sku=sku, store_id=store_id)

    evidence = {"analysis": analysis}
    if sku is None and "investigat" in q_lower:
        evidence["note"] = (
            "No specific SKU was mentioned, so this is a catalog-wide scan; "
            "see products_requiring_investigation for the count flagged."
        )
    return evidence


def answer_question(question, service=None):
    """Answer a natural-language inventory-vs-forecast question.

    Returns a dict with keys: configured, question, evidence, answer,
    message. The API key is never included in the return value.
    """
    service = service or _default_service
    evidence = _gather_evidence(question, service)

    if not is_configured():
        return {
            "configured": False,
            "question": question,
            "evidence": evidence,
            "answer": None,
            "message": (
                "OPENAI_API_KEY is not set, so no natural-language explanation "
                "was generated. The deterministic evidence below was computed "
                "directly from the data via direct Python calls to both agents. "
                "Copy .env.example to .env and set a real OPENAI_API_KEY (and "
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


_BASE_RESULT_NARRATION_SYSTEM_PROMPT = """\
You are a retail operations assistant narrating an already-computed \
structured result from the Retail Intelligence Orchestrator. All data is \
synthetic test data generated for development.

You will be given the user's question and a JSON "result" object computed \
deterministically by Python, by calling one or more of the Inventory, \
Demand Forecasting, Promotion, Order Fulfillment, and Customer Experience \
agents. You did not compute any of these numbers and must not recompute, \
adjust, or second-guess any of them.

Rules:
- Write a short, plain-language narrative (2-5 sentences) explaining the \
result's key_findings, severity, and recommended_actions to a retail \
operations reader.
- Never invent a SKU, order ID, store ID, quantity, date, or figure that is \
not already present in the result.
- If data_gaps_and_uncertainty is non-empty, mention that some information \
could not be determined -- do not paper over it.
- Every recommended action is read-only and requires human approval -- \
never phrase anything as already done or as something you will do.
- Keep it concise. Do not repeat the raw JSON back verbatim.
"""


def _result_narration_system_prompt():
    """_BASE_RESULT_NARRATION_SYSTEM_PROMPT, plus the most recent
    AI-feedback-loop prompt adjustment for this agent (agent_feedback/
    retuning.py), if one has been triggered by accumulated negative user
    feedback. This is the prompt actually used by POST /retail-ai/query --
    the only live HTTP path that produces an LLM narration today -- so a
    retune here is the one observable end-to-end by re-asking a question
    on the Ask Retail AI page."""
    adjustment = get_active_adjustment(AGENT_KEY)
    if not adjustment:
        return _BASE_RESULT_NARRATION_SYSTEM_PROMPT
    return f"{_BASE_RESULT_NARRATION_SYSTEM_PROMPT}\n{adjustment}\n"


def narrate_orchestrator_result(question, result):
    """Optionally narrate an already-computed RetailIntelligenceOrchestrator
    result (see orchestration/query_orchestrator.py::handle_query) in
    natural language. Never recomputes anything -- the model only explains
    the structured `result` dict it is given, the same "explain, don't
    compute" pattern as answer_question() above.

    Returns a dict with keys: configured, answer, message. Never raises --
    a missing API key or any OpenAI API failure is caught and reported via
    `message` instead, so narration is always a non-blocking enrichment on
    top of the deterministic result, never a dependency of it."""
    if not is_configured():
        return {
            "configured": False,
            "answer": None,
            "message": (
                "OPENAI_API_KEY is not set, so no natural-language narration was "
                "generated. The structured result above was computed deterministically."
            ),
        }

    try:
        client = get_openai_client()
        model = get_openai_model()
        response = client.chat.completions.create(
            model=model,
            temperature=0,
            messages=[
                {"role": "system", "content": _result_narration_system_prompt()},
                {
                    "role": "user",
                    "content": f"Question: {question}\n\nResult (JSON):\n{json.dumps(result, indent=2, default=str)}",
                },
            ],
        )
        return {"configured": True, "answer": response.choices[0].message.content, "message": None}
    except Exception as exc:
        return {
            "configured": True,
            "answer": None,
            "message": f"Natural-language narration failed ({type(exc).__name__}); showing the structured result only.",
        }
