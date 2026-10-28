"""
Omnichannel Retail AI Command Center -- Streamlit entry point.

Run with:
    streamlit run dashboard/app.py

This file and everything in dashboard/pages/ are UI-only: all calculations
come from the existing agents via dashboard/data_prep.py and the shared
RetailIntelligenceOrchestrator (dashboard/state.py). No business logic is
reimplemented here, and nothing in this dashboard writes to any dataset,
database, or external API -- every view is read-only.
"""

import sys
from pathlib import Path

import streamlit as st

# Allow running via `streamlit run dashboard/app.py` from the project root
# without needing the project installed as a package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dashboard.data_prep import build_command_center
from dashboard.state import get_orchestrator
from dashboard.ui_components import (
    data_freshness_note,
    data_gaps_panel,
    disclaimer_footer,
    empty_state,
    error_state,
    severity_label,
)

st.set_page_config(
    page_title="Omnichannel Retail AI Command Center",
    page_icon="🛍️",
    layout="wide",
)

st.title("🛍️ Omnichannel Retail AI Command Center")
st.caption("Use the sidebar to open Inventory & Demand, Promotion Intelligence, Order Fulfillment, Customer Experience, or Ask Retail AI.")

orchestrator = get_orchestrator()

with st.sidebar:
    st.header("Controls")
    horizon_days = st.slider("Promotion lookahead (days)", min_value=1, max_value=60, value=7)
    if st.button("🔄 Refresh data"):
        st.cache_data.clear()
        st.rerun()

data = build_command_center(orchestrator, days_ahead=horizon_days)

data_freshness_note(data["dataset_note"])
st.subheader(f"Overall severity: {severity_label(data['severity'])}")
data_gaps_panel(data["data_gaps"])

st.divider()
st.subheader("Key Performance Indicators")

inv = data["inventory_summary"]
demand = data["demand_summary"]
promo = data["promotion_summary"]
fulfillment = data["fulfillment_summary"]
cx = data["cx_summary"]

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric(
        "Total Active (Open) Orders",
        fulfillment["total_open_orders"] if fulfillment else "Unavailable",
    )
with col2:
    st.metric(
        "Inventory Stockout Risks (critical+high)",
        (inv["risk_level_counts"].get("critical", 0) + inv["risk_level_counts"].get("high", 0)) if inv else "Unavailable",
    )
with col3:
    st.metric(
        "Products with Excess Inventory",
        inv["products_with_excess_inventory"] if inv else "Unavailable",
    )
with col4:
    st.metric(
        "Customer-Impacting Issues",
        cx["total_customer_impact_risks"] if cx else "Unavailable",
    )

col5, col6, col7, col8 = st.columns(4)
with col5:
    st.metric(
        "Orders at Risk of Late Delivery",
        fulfillment["risk_counts"].get("critical", 0) + fulfillment["risk_counts"].get("high", 0) if fulfillment else "Unavailable",
    )
with col6:
    st.metric(
        f"Upcoming Promotions (next {horizon_days}d)",
        data["upcoming_promotions_count"] if data["upcoming_promotions_count"] is not None else "Unavailable",
    )
with col7:
    st.metric(
        "Demand Spikes Detected",
        demand["products_with_demand_spike"] if demand else "Unavailable",
    )
with col8:
    st.metric(
        "Promotions Insufficiently Stocked",
        promo["readiness_counts"].get("insufficient", 0) if promo else "Unavailable",
    )

st.divider()
st.subheader("Key Findings")
if data["key_findings"]:
    for finding in data["key_findings"]:
        st.markdown(f"- {finding}")
else:
    empty_state("No key findings available right now.")

st.subheader("Recommended Actions Requiring Human Review")
recovery = data["recommended_actions"]
if recovery and recovery.get("orders"):
    st.caption(f"{recovery['total_orders_with_recommendations']} order(s) have at least one recommended action.")
    for action, count in sorted(recovery["action_counts"].items(), key=lambda kv: -kv[1]):
        st.markdown(f"- **{count}×** {action}")
else:
    empty_state("No recommended actions at this time.")

disclaimer_footer()
