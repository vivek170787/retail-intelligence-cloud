"""
The "automatic" half of the AI feedback loop: once enough negative
feedback has accumulated for one agent_key, synthesize a corrective note
and persist it as a new prompt_adjustments row (agent_feedback/store.py).
Every agent's llm_explainer.py reads the latest adjustment for its own
agent_key and appends it to its system prompt on the next call -- so this
module is what actually makes "negative feedback changes future answers"
true, not just logged.

Deliberately template-based rather than a second LLM call: this keeps the
loop deterministic, free, and functional even when OPENAI_API_KEY is not
set, consistent with the rest of the project's "deterministic core,
optional LLM enrichment" split (see e.g. demand_forecasting_agent/
llm_explainer.py's module docstring).
"""

from agent_feedback.store import create_adjustment, list_uncounted_negative_feedback

NEGATIVE_FEEDBACK_THRESHOLD = 3

_MAX_COMMENTS_IN_ADJUSTMENT = 5
_COMMENT_TRUNCATE_CHARS = 150

_GENERIC_FALLBACK_NOTE = (
    "Users have flagged recent answers from this agent as unhelpful or "
    "incorrect, but did not leave specific comments. Double-check that "
    "every claim is directly supported by the evidence provided, keep the "
    "answer specific and concise, and say plainly when evidence is "
    "insufficient rather than guessing."
)


def _synthesize_adjustment_text(negative_rows):
    comments = []
    seen = set()
    for row in negative_rows:
        comment = (row.get("comment") or "").strip()
        if comment and comment not in seen:
            seen.add(comment)
            comments.append(comment[:_COMMENT_TRUNCATE_CHARS])
        if len(comments) >= _MAX_COMMENTS_IN_ADJUSTMENT:
            break

    if not comments:
        return f"CORRECTIVE NOTE (auto-generated from {len(negative_rows)} negative user ratings): {_GENERIC_FALLBACK_NOTE}"

    quoted = "; ".join(f"'{c}'" for c in comments)
    return (
        f"CORRECTIVE NOTE (auto-generated from {len(negative_rows)} negative user ratings): "
        f"users flagged recent answers as unhelpful or incorrect, raising these concerns: "
        f"{quoted}. Address these specific concerns directly in future answers, and keep "
        f"every claim grounded in the evidence provided."
    )


def maybe_retune(agent_key):
    """Check whether agent_key has crossed NEGATIVE_FEEDBACK_THRESHOLD
    uncounted negative feedback rows, and if so, create a new prompt
    adjustment and mark those rows as counted. No-op (no DB write) if the
    threshold has not been met."""
    uncounted = list_uncounted_negative_feedback(agent_key)
    if len(uncounted) < NEGATIVE_FEEDBACK_THRESHOLD:
        return {
            "retuned": False,
            "agent_key": agent_key,
            "reason": "threshold_not_met",
            "uncounted_negative_count": len(uncounted),
        }

    adjustment_text = _synthesize_adjustment_text(uncounted)
    adjustment_id = create_adjustment(
        agent_key=agent_key,
        adjustment_text=adjustment_text,
        trigger_feedback_count=len(uncounted),
        feedback_ids_to_mark=[row["id"] for row in uncounted],
    )
    return {
        "retuned": True,
        "agent_key": agent_key,
        "adjustment_id": adjustment_id,
        "adjustment_text": adjustment_text,
        "trigger_feedback_count": len(uncounted),
    }


def force_retune(agent_key):
    """Manually trigger a retune regardless of threshold -- backs a
    "Force retune" demo/admin action. Uses whatever uncounted negative
    feedback currently exists (even zero, via the generic fallback note)
    so a demo doesn't require submitting exactly N organic thumbs-down."""
    uncounted = list_uncounted_negative_feedback(agent_key)
    adjustment_text = _synthesize_adjustment_text(uncounted)
    adjustment_id = create_adjustment(
        agent_key=agent_key,
        adjustment_text=adjustment_text,
        trigger_feedback_count=len(uncounted),
        feedback_ids_to_mark=[row["id"] for row in uncounted],
    )
    return {
        "retuned": True,
        "agent_key": agent_key,
        "adjustment_id": adjustment_id,
        "adjustment_text": adjustment_text,
        "trigger_feedback_count": len(uncounted),
        "forced": True,
    }
