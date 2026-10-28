"""Order Fulfillment dashboard page."""

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from dashboard.data_prep import (
    build_alternative_fulfillment_options,
    build_fulfillment_priorities_table,
    build_inventory_blocked_orders_table,
    build_order_fulfillment_detail,
    build_orders_at_risk_table,
    build_orders_due_today_table,
)
from dashboard.state import get_orchestrator
from dashboard.ui_components import csv_download_button, disclaimer_footer, empty_state, error_state, severity_label

st.set_page_config(page_title="Order Fulfillment", page_icon="🚚", layout="wide")
st.title("🚚 Order Fulfillment")

orchestrator = get_orchestrator()

tab1, tab2, tab3 = st.tabs(["Orders at Risk", "Due Today / Overdue", "Inventory-Blocked"])

with tab1:
    priorities_df, priorities_error = build_fulfillment_priorities_table(orchestrator, limit=20)
    if priorities_error:
        error_state(priorities_error)
    elif priorities_df.empty:
        empty_state("No orders currently at risk.")
    else:
        st.dataframe(priorities_df, width="stretch", hide_index=True)
        csv_download_button(priorities_df, "Export at-risk orders (CSV)", "orders_at_risk.csv")

with tab2:
    due_df, due_error = build_orders_due_today_table(orchestrator)
    if due_error:
        error_state(due_error)
    elif due_df.empty:
        empty_state("No orders due today or overdue.")
    else:
        st.dataframe(due_df, width="stretch", hide_index=True)
        csv_download_button(due_df, "Export due/overdue orders (CSV)", "orders_due_today.csv")

with tab3:
    blocked_df, blocked_error = build_inventory_blocked_orders_table(orchestrator)
    if blocked_error:
        error_state(blocked_error)
    elif blocked_df.empty:
        empty_state("No orders are currently blocked by an inventory shortage.")
    else:
        st.dataframe(blocked_df, width="stretch", hide_index=True)
        csv_download_button(blocked_df, "Export inventory-blocked orders (CSV)", "orders_inventory_blocked.csv")

st.divider()
st.subheader("Order Detail & Alternative Fulfillment Options")

order_id = st.text_input("Enter an order ID (e.g. ORD-000103)", key="fulfillment_order_id")
if order_id:
    detail, detail_error = build_order_fulfillment_detail(orchestrator, order_id)
    if detail_error:
        error_state(detail_error)
    elif not detail.get("order_found", True):
        empty_state(detail.get("note", "Order not found."))
    else:
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**Risk level:** {severity_label(detail['risk_level'])}")
            st.markdown(f"**Status:** {detail['order_status']}  |  **SKU:** {detail['sku']}  |  **Location:** {detail['fulfillment_location']}")
            st.markdown(f"**Promised delivery date:** {detail.get('promised_delivery_date') or 'Missing'}")
            if detail.get("days_overdue"):
                st.warning(f"Overdue by {detail['days_overdue']} day(s).")
            st.markdown("**Recommended next actions:**")
            if detail.get("recommendations"):
                for rec in detail["recommendations"]:
                    st.markdown(f"- {rec}")
            else:
                empty_state("No specific recommendations.")
        with col2:
            st.markdown(f"**Delivery feasibility:** {detail['delivery_feasibility']['status']}")
            st.caption(detail["delivery_feasibility"]["reason"])
            with st.expander("Full evidence (raw)"):
                st.json(detail)

        st.markdown("**Available alternative fulfillment options, if supported:**")
        alt_df, alt_result, alt_error = build_alternative_fulfillment_options(orchestrator, order_id)
        if alt_error:
            error_state(alt_error)
        elif alt_df.empty:
            empty_state("No alternative fulfillment candidates found.")
        else:
            st.dataframe(alt_df, width="stretch", hide_index=True)
            st.caption(alt_result.get("disclaimer", ""))

disclaimer_footer()
