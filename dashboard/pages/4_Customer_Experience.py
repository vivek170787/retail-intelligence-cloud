"""Customer Experience dashboard page.

Displays only the synthetic customer_id already present in the project's
data -- no name, email, address, or other personal information exists
anywhere in this dataset, so there is nothing further to mask.
"""

import sys
from pathlib import Path

import plotly.express as px
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from dashboard.data_prep import (
    build_at_risk_customer_orders_table,
    build_customer_impact_risks_table,
    build_customer_order_experience_detail,
    build_service_recovery_recommendations,
)
from dashboard.state import get_orchestrator
from dashboard.ui_components import csv_download_button, disclaimer_footer, empty_state, error_state, severity_label

st.set_page_config(page_title="Customer Experience", page_icon="💬", layout="wide")
st.title("💬 Customer Experience")

orchestrator = get_orchestrator()

risks_df, risks_error = build_customer_impact_risks_table(orchestrator)
if risks_error:
    error_state(risks_error)
elif risks_df.empty:
    empty_state("No customer-impacting order risks right now.")
else:
    col1, col2 = st.columns([2, 1])
    with col1:
        severity_filter = st.multiselect(
            "Filter by severity",
            options=sorted(risks_df["severity"].unique()),
            default=list(sorted(risks_df["severity"].unique())),
        )
        review_only = st.checkbox("Only show orders flagged for potential cancellation risk")
        filtered = risks_df[risks_df["severity"].isin(severity_filter)]
        if review_only:
            filtered = filtered[filtered["potential_cancellation_risk"]]
        st.dataframe(filtered, width="stretch", hide_index=True)
        csv_download_button(filtered, "Export customer impact risks (CSV)", "customer_impact_risks.csv")
    with col2:
        fig = px.pie(risks_df, names="severity", title="Customer Impact by Severity")
        st.plotly_chart(fig, width="stretch")

st.divider()
st.subheader("Recommended Service Recovery Actions")
recovery, recovery_error = build_service_recovery_recommendations(orchestrator)
if recovery_error:
    error_state(recovery_error)
elif not recovery or not recovery.get("orders"):
    empty_state("No service recovery actions currently recommended.")
else:
    st.caption(f"{recovery['total_orders_with_recommendations']} order(s) have at least one recommended action.")
    for action, count in sorted(recovery["action_counts"].items(), key=lambda kv: -kv[1]):
        st.markdown(f"- **{count}×** {action}")

st.divider()
st.subheader("Order Detail")
order_id = st.text_input("Enter an order ID (e.g. ORD-000103)", key="cx_order_id")
if order_id:
    detail, detail_error = build_customer_order_experience_detail(orchestrator, order_id)
    if detail_error:
        error_state(detail_error)
    elif not detail.get("order_found", True):
        empty_state(detail.get("note", "Order not found."))
    else:
        st.markdown(f"**Severity:** {severity_label(detail['severity'])}  |  **Problem type:** {detail['problem_type']}")
        st.markdown(f"**Customer ID (synthetic):** {detail.get('customer_id')}  |  **SKU:** {detail.get('sku')}")
        st.markdown(f"**Explanation:** {detail['explanation']}")

        cancellation = detail.get("potential_cancellation_risk") or {}
        if cancellation.get("flagged"):
            st.warning(f"⚠️ Potential cancellation risk flagged: {cancellation['reason']}")

        st.markdown("**Recommended actions:**")
        for action in detail.get("recommended_actions", []) or []:
            st.markdown(f"- {action}")

        alt_product = detail.get("alternative_product_recommendation") or {}
        if not alt_product.get("available"):
            st.caption(f"Alternative product recommendation: not available -- {alt_product.get('reason')}")

        human_action = detail.get("human_reviewed_recovery_action") or {}
        if human_action.get("suggested"):
            st.info(f"Human-reviewed recovery action may be warranted. {human_action.get('reason')}")

        marketplace = detail.get("marketplace_context")
        if marketplace and marketplace.get("any_availability_issue"):
            st.caption(f"Marketplace availability context: {marketplace.get('note')}")

        with st.expander("Full evidence (raw)"):
            st.json(detail)

disclaimer_footer()
