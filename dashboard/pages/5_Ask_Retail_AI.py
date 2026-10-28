"""
Ask Retail AI -- natural-language retail query page.

Routes every question through the existing RetailIntelligenceOrchestrator
.handle_query() (orchestration/query_orchestrator.py). That routing is
already fully deterministic (keyword + SKU/order/store-ID pattern
matching) -- no OpenAI API key is involved anywhere on this page, and none
is required for any of the example questions below. This page does not
duplicate the orchestrator's routing logic or introduce a second agent
framework; it only renders the structured dict it returns.
"""

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from dashboard.data_prep import run_retail_query
from dashboard.state import get_orchestrator
from dashboard.ui_components import data_gaps_panel, disclaimer_footer, empty_state, error_state, severity_badge

st.set_page_config(page_title="Ask Retail AI", page_icon="🤖", layout="wide")
st.title("🤖 Ask Retail AI")
st.caption(
    "Deterministic business-query routing through the existing Retail Intelligence "
    "Orchestrator -- no OpenAI API key required for this page."
)

orchestrator = get_orchestrator()

EXAMPLE_QUESTIONS = [
    "Which stores are at risk of stockouts this week?",
    "Which promotions are not inventory-ready?",
    "Which orders need immediate attention?",
    "What actions could reduce lost sales?",
    "Give me today's retail risk summary.",
]

st.markdown("**Example questions:**")
cols = st.columns(len(EXAMPLE_QUESTIONS))
clicked = None
for col, question in zip(cols, EXAMPLE_QUESTIONS):
    if col.button(question, width="stretch"):
        clicked = question

query_text = st.text_input("Or type your own retail question:", value=clicked or "")

if query_text:
    result, error = run_retail_query(orchestrator, query_text)
    if error:
        error_state(error)
    elif result is None:
        empty_state("Please enter a question.")
    else:
        st.divider()
        st.markdown(f"**Category:** `{result['category']}`")
        severity_badge(result["severity"])
        st.markdown(f"### {result['summary']}")

        if result["key_findings"]:
            st.markdown("**Key findings:**")
            for finding in result["key_findings"]:
                st.markdown(f"- {finding}")

        affected = result["affected_entities"]
        if any(affected.values()):
            st.markdown("**Affected entities:**")
            if affected["skus"]:
                st.markdown(f"- SKUs: {', '.join(affected['skus'][:20])}")
            if affected["stores"]:
                st.markdown(f"- Stores: {', '.join(affected['stores'][:20])}")
            if affected["orders"]:
                st.markdown(f"- Orders: {', '.join(affected['orders'][:20])}")

        if result["recommended_actions"]:
            st.markdown("**Recommended actions (human review required):**")
            for action in result["recommended_actions"]:
                st.markdown(f"- {action}")
        else:
            empty_state("No specific recommended actions for this query.")

        data_gaps_panel(result["data_gaps_and_uncertainty"])

        with st.expander("Supporting evidence (raw)"):
            st.json(result["evidence"])

        st.caption(f"Agents consulted: {', '.join(result['agents_used']) or 'none'}")

disclaimer_footer()
