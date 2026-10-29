"""Promotion Intelligence dashboard page."""

import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from dashboard.data_prep import (
    build_demand_spikes_table,
    build_promotion_readiness,
    build_upcoming_promotions_table,
    flatten_readiness_report,
)
from dashboard.state import get_orchestrator
from dashboard.ui_components import csv_download_button, empty_state, error_state, render_evidence, severity_label

st.set_page_config(page_title="Promotion Intelligence", page_icon="🏷️", layout="wide")
st.title("🏷️ Promotion Intelligence")

orchestrator = get_orchestrator()

days_ahead = st.slider("Lookahead window (days)", min_value=1, max_value=90, value=14)

st.subheader(f"Upcoming Promotions (next {days_ahead} days)")
upcoming_df, upcoming_error = build_upcoming_promotions_table(orchestrator, days_ahead=days_ahead)
if upcoming_error:
    error_state(upcoming_error)
elif upcoming_df.empty:
    empty_state("No promotions starting in this window.")
else:
    st.dataframe(upcoming_df, width="stretch", hide_index=True)
    csv_download_button(upcoming_df, "Export upcoming promotions (CSV)", "upcoming_promotions.csv")

st.divider()
st.subheader("Promotion Readiness")
report, readiness_error = build_promotion_readiness(orchestrator, days_ahead=days_ahead)
if readiness_error:
    error_state(readiness_error)
elif not report or not report["reports"]:
    empty_state("No upcoming/active promotions to assess readiness for.")
else:
    readiness_df = pd.DataFrame([flatten_readiness_report(r) for r in report["reports"]])
    status_filter = st.multiselect(
        "Filter by readiness status",
        options=sorted(readiness_df["readiness_status"].unique()),
        default=list(sorted(readiness_df["readiness_status"].unique())),
    )
    filtered = readiness_df[readiness_df["readiness_status"].isin(status_filter)]
    st.dataframe(filtered, width="stretch", hide_index=True)
    csv_download_button(filtered, "Export readiness report (CSV)", "promotion_readiness.csv")

    insufficient = readiness_df[readiness_df["readiness_status"] == "insufficient"]
    if not insufficient.empty:
        st.markdown("**Products with insufficient inventory for expected demand:**")
        for _, row in insufficient.iterrows():
            st.markdown(
                f"- `{row['sku']}` (promotion `{row['promotion_id']}`): "
                f"gap of {row['demand_gap']} units -- {severity_label(row['readiness_status'])}"
            )

    with st.expander("Supporting evidence and assumptions"):
        for r in report["reports"]:
            st.markdown(f"**{r['sku']} / {r['promotion_id']}**")
            render_evidence(r)

st.divider()
st.subheader("Potential Demand Spikes")
st.caption("Cross-referenced from the Demand Forecasting Agent -- a statistical trigger, not proof of a promotional cause.")
spikes_df, spikes_error = build_demand_spikes_table(orchestrator)
if spikes_error:
    error_state(spikes_error)
elif spikes_df.empty:
    empty_state("No demand spikes detected.")
else:
    st.dataframe(spikes_df, width="stretch", hide_index=True)
    fig = px.bar(spikes_df, x="sku", y="percent_change", title="Demand Spikes by % Change")
    st.plotly_chart(fig, width="stretch")
