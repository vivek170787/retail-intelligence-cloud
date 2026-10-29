"""
LLM-as-judge quality scoring for the Agent Evaluation workspace.

A second, independent OpenAI call -- its own JUDGE_SYSTEM_PROMPT, never the
agent's own system prompt -- that scores an already-generated answer
against the evidence it was supposedly grounded in. Reuses the project's
shared openai_config.py client exactly like every llm_explainer.py does.

Never raises: a missing API key, a malformed/unparseable judge response, or
any OpenAI API failure all result in the same `judged: False` shape with
`error` populated, mirroring orchestration/llm_explainer.py's
narrate_orchestrator_result()'s existing try/except Exception pattern.
"""

import json
import re

from openai_config import get_openai_client, get_openai_model, is_configured

JUDGE_SYSTEM_PROMPT = """\
You are a strict, impartial evaluator of a retail-intelligence assistant's \
natural-language answer. All data is synthetic test data generated for \
development.

You will be given the user's question, a JSON "evidence" object that was \
computed deterministically by Python (the only legitimate source of facts), \
and the assistant's natural-language "answer".

Score the answer on three dimensions, each as an integer from 1 (very poor) \
to 5 (excellent):
- groundedness: does the answer avoid inventing any fact, number, SKU, \
order ID, or figure not present in the evidence?
- relevance: does the answer actually address the question asked?
- clarity: is the answer clear, concise, and easy for a retail operations \
reader to act on?

Respond with ONLY a bare JSON object (no markdown fences, no extra text) \
with exactly these keys: "groundedness", "relevance", "clarity" (each an \
integer 1-5), and "rationale" (one concise sentence explaining the scores).
"""

_JSON_OBJECT_PATTERN = re.compile(r"\{.*\}", re.DOTALL)

_SCORE_KEYS = ("groundedness", "relevance", "clarity")


def _not_judged(error):
    return {"judged": False, "scores": None, "overall": None, "rationale": None, "error": error}


def _parse_judge_response(raw_text):
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError:
        match = _JSON_OBJECT_PATTERN.search(raw_text)
        if not match:
            raise ValueError("judge response contained no JSON object")
        data = json.loads(match.group(0))

    scores = {}
    for key in _SCORE_KEYS:
        value = data.get(key)
        if not isinstance(value, int) or not (1 <= value <= 5):
            raise ValueError(f"judge response field {key!r} is not an integer in [1, 5]: {value!r}")
        scores[key] = value

    rationale = data.get("rationale")
    if not isinstance(rationale, str) or not rationale.strip():
        raise ValueError("judge response is missing a non-empty 'rationale' string")

    return scores, rationale.strip()


def judge_answer(question, evidence, answer):
    """Score `answer` (the natural-language text an agent generated for
    `question`, given `evidence`) for groundedness/relevance/clarity.

    Returns {judged, scores, overall, rationale, error}. Skips the call
    entirely (no API cost) when not is_configured() or answer is None.
    `overall` is computed in Python as the mean of the three scores --
    never asked of the model, so there's one fewer field it could botch.
    """
    if not is_configured():
        return _not_judged("OPENAI_API_KEY is not set; judge call skipped.")
    if answer is None:
        return _not_judged("No answer was generated for this question; judge call skipped.")

    try:
        client = get_openai_client()
        model = get_openai_model()
        response = client.chat.completions.create(
            model=model,
            temperature=0,
            messages=[
                {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Question: {question}\n\n"
                        f"Evidence (JSON):\n{json.dumps(evidence, indent=2, default=str)}\n\n"
                        f"Answer:\n{answer}"
                    ),
                },
            ],
        )
        raw_text = response.choices[0].message.content
        scores, rationale = _parse_judge_response(raw_text)
        overall = round(sum(scores[k] for k in _SCORE_KEYS) / len(_SCORE_KEYS), 2)
        return {"judged": True, "scores": scores, "overall": overall, "rationale": rationale, "error": None}
    except Exception as exc:
        return _not_judged(f"Judge call failed ({type(exc).__name__}): {exc}")
