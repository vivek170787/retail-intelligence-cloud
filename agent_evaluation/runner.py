"""
Agent Evaluation runner: executes every (or one agent's) hardcoded test
case from agent_evaluation/test_cases.py against the REAL agent code --
never a mock or a fabricated answer -- scores it with a rubric check
(evidence presence + answer keyword check) and an LLM-as-judge call
(agent_evaluation/judge.py), and writes one row per test case via
agent_evaluation/eval_log.py.

Dispatch: for each of the 5 domain agents, calls that module's own
answer_question(question) directly (uses its module-level
_default_engine -- the exact function each agent's own cli.py and tests
already call). For "orchestrator", calls
orchestration.query_orchestrator.handle_query(question) for the
structured result's evidence, then
orchestration.llm_explainer.narrate_orchestrator_result(question, result)
for the answer -- the same two-step flow api/routers/retail_ai.py uses for
the one live HTTP path that actually narrates a question end-to-end.
"""

import uuid

import customer_experience_agent.llm_explainer as cx_explainer
import demand_forecasting_agent.llm_explainer as demand_explainer
import inventory_agent.llm_explainer as inventory_explainer
import order_fulfillment_agent.llm_explainer as fulfillment_explainer
import promotion_agent.llm_explainer as promotion_explainer
import orchestration.llm_explainer as orchestrator_explainer
from agent_evaluation import eval_log
from agent_evaluation.judge import judge_answer
from agent_evaluation.test_cases import TEST_CASES, TEST_CASES_BY_AGENT
from orchestration.query_orchestrator import handle_query as orchestrator_handle_query

_DOMAIN_EXPLAINERS = {
    "inventory": inventory_explainer,
    "demand": demand_explainer,
    "promotion": promotion_explainer,
    "fulfillment": fulfillment_explainer,
    "customer_experience": cx_explainer,
}


def _resolve_dot_path(evidence, dot_path):
    """Resolve a "a.b.c" dot-path against a nested dict, returning the
    value, or a sentinel _MISSING if any segment is absent or the value
    along the way is None."""
    current = evidence
    for segment in dot_path.split("."):
        if not isinstance(current, dict) or segment not in current:
            return _MISSING
        current = current[segment]
        if current is None:
            return _MISSING
    return current


_MISSING = object()


def _check_evidence(evidence, expected_evidence_keys):
    missing = [key for key in expected_evidence_keys if _resolve_dot_path(evidence, key) is _MISSING]
    return (len(missing) == 0), missing


def _check_keywords(answer, answer_keywords_any):
    if not answer_keywords_any:
        return True
    answer_lower = answer.lower()
    return any(term in answer_lower for term in answer_keywords_any)


def _run_domain_agent(agent_key, question):
    explainer = _DOMAIN_EXPLAINERS[agent_key]
    result = explainer.answer_question(question)
    return result["evidence"], result["answer"]


def _run_orchestrator(question):
    result = orchestrator_handle_query(question)
    narration = orchestrator_explainer.narrate_orchestrator_result(question, result)
    return result.get("evidence") or {}, narration["answer"]


def _run_one_test_case(run_id, test_case):
    agent_key = test_case["agent_key"]
    question = test_case["question"]

    if agent_key == "orchestrator":
        evidence, answer = _run_orchestrator(question)
    else:
        evidence, answer = _run_domain_agent(agent_key, question)

    evidence_passed, missing_keys = _check_evidence(evidence, test_case["expected_evidence_keys"])

    if answer is None:
        status = "skipped_no_answer"
        keyword_passed = True
        judge_result = {"judged": False, "scores": None, "overall": None, "rationale": None,
                         "error": "No answer was generated for this question; judge call skipped."}
    else:
        status = "checked"
        keyword_passed = _check_keywords(answer, test_case["answer_keywords_any"])
        judge_result = judge_answer(question, evidence, answer)

    passed = evidence_passed and keyword_passed

    eval_log.insert_result(
        run_id=run_id,
        agent_key=agent_key,
        test_case_id=test_case["id"],
        question=question,
        status=status,
        evidence_passed=evidence_passed,
        missing_evidence_keys=missing_keys,
        keyword_passed=keyword_passed,
        passed=passed,
        judged=judge_result["judged"],
        judge_scores=judge_result["scores"],
        judge_overall=judge_result["overall"],
        judge_rationale=judge_result["rationale"],
        judge_error=judge_result["error"],
    )

    return {
        "run_id": run_id,
        "agent_key": agent_key,
        "test_case_id": test_case["id"],
        "question": question,
        "status": status,
        "evidence_passed": evidence_passed,
        "missing_evidence_keys": missing_keys,
        "keyword_passed": keyword_passed,
        "passed": passed,
        **judge_result,
    }


def run_evaluations(agent_key=None):
    """Run every test case (optionally filtered to one agent_key), writing
    one eval_results row per case under a single new run_id. Returns the
    list of result dicts produced by this run."""
    eval_log.init_db()
    cases = TEST_CASES_BY_AGENT.get(agent_key, []) if agent_key else TEST_CASES
    run_id = uuid.uuid4().hex[:12]
    return [_run_one_test_case(run_id, case) for case in cases]
