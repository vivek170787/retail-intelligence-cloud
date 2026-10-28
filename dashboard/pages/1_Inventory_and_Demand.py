"""Inventory & Demand dashboard page."""

import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from dashboard.data_prep import (
    build_demand_forecast,
    build_inventory_table,
    build_replenishment_table,
    build_sales_history_series,
    build_store_breakdown,
    build_top_forecasted_products,
)
from dashboard.state import get_orchestrator
from dashboard.ui_components import csv_download_button, empty_state, error_state, severity_label

st.set_page_config(page_title="Inventory & Demand", page_icon="📦", layout="wide")
st.title("📦 Inventory & Demand")

orchestrator = get_orchestrator()

inventory_df, inv_error = build_inventory_table(orchestrator)
if inv_error:
    error_state(f"Could not load inventory risk data: {inv_error}")

st.subheader("Inventory by SKU -- Stockout Risk")
if inventory_df.empty:
    empty_state("No inventory data available.")
else:
    risk_filter = st.multiselect(
        "Filter by risk level",
        options=sorted(inventory_df["risk_level"].unique()),
        default=list(sorted(inventory_df["risk_level"].unique())),
    )
    filtered = inventory_df[inventory_df["risk_level"].isin(risk_filter)]
    st.dataframe(filtered, width="stretch", hide_index=True)
    csv_download_button(filtered, "Export inventory table (CSV)", "inventory_risk.csv")

    fig = px.bar(
        inventory_df["risk_level"].value_counts().reset_index(),
        x="risk_level", y="count", title="Products by Risk Level",
        color="risk_level",
        color_discrete_map={"critical": "#D32F2F", "high": "#F57C00", "medium": "#FBC02D", "low": "#388E3C", "unable_to_assess": "#9E9E9E"},
    )
    st.plotly_chart(fig, width="stretch")

st.divider()
st.subheader("Store-Level Breakdown & Demand Forecast")

skus = sorted(inventory_df["sku"].unique()) if not inventory_df.empty else []
selected_sku = st.selectbox("Select a SKU for detail", options=skus) if skus else None

if selected_sku:
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Inventory by store**")
        store_df, product_analysis, store_error = build_store_breakdown(orchestrator, selected_sku)
        if store_error:
            error_state(store_error)
        elif store_df.empty:
            empty_state("No store-level inventory data for this SKU.")
        else:
            st.dataframe(store_df, width="stretch", hide_index=True)
            if product_analysis:
                st.markdown(
                    f"**Days of inventory remaining:** {product_analysis['estimated']['days_of_inventory']} &nbsp;&nbsp; "
                    f"**Risk level:** {severity_label(product_analysis['estimated']['risk_level'])}"
                )
                with st.expander("Full evidence (raw)"):
                    st.json(product_analysis)

    with col2:
        st.markdown("**Recent sales trend & demand forecast**")
        horizon = st.number_input("Forecast horizon (days)", min_value=1, max_value=60, value=7, key="horizon_inv")
        series, series_error = build_sales_history_series(orchestrator, selected_sku)
        forecast, forecast_error = build_demand_forecast(orchestrator, selected_sku, horizon_days=horizon)
        if series_error:
            error_state(series_error)
        elif series.empty:
            empty_state("No confirmed sales history for this SKU.")
        else:
            hist_df = series.reset_index()
            hist_df.columns = ["date", "units"]
            hist_df["series"] = "historical"
            chart_frames = [hist_df]
            if forecast and forecast.get("sufficient_data") and forecast.get("forecast_daily"):
                future_dates = pd.date_range(
                    forecast["forecast_start_date"], periods=len(forecast["forecast_daily"])
                )
                fc_df = pd.DataFrame({"date": future_dates, "units": forecast["forecast_daily"], "series": "forecast"})
                chart_frames.append(fc_df)
            fig2 = px.line(pd.concat(chart_frames), x="date", y="units", color="series", title=f"{selected_sku}: history + forecast")
            st.plotly_chart(fig2, width="stretch")
            if forecast and forecast.get("sufficient_data"):
                st.markdown(f"**Total forecast demand ({horizon}d):** {forecast['total_forecast_demand']} (method: {forecast['forecast_method']})")
            elif forecast:
                empty_state(f"Forecast unavailable: {forecast.get('reason')}")

st.divider()
st.subheader("Replenishment Recommendations")
repl_df, repl_error = build_replenishment_table(orchestrator)
if repl_error:
    error_state(repl_error)
elif repl_df.empty:
    empty_state("No SKUs currently need replenishment.")
else:
    st.dataframe(repl_df, width="stretch", hide_index=True)
    csv_download_button(repl_df, "Export replenishment recommendations (CSV)", "replenishment_recommendations.csv")

st.divider()
st.subheader("Top Forecasted Demand (next 7 days)")
top_df, top_error = build_top_forecasted_products(orchestrator, horizon_days=7, limit=10)
if top_error:
    error_state(top_error)
elif top_df.empty:
    empty_state("No forecast data available.")
else:
    fig3 = px.bar(top_df, x="sku", y="total_forecast_demand", hover_data=["product_name"], title="Top 10 SKUs by Forecast Demand")
    st.plotly_chart(fig3, width="stretch")
