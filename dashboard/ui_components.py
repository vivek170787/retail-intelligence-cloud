"""
Reusable Streamlit UI helpers shared across every dashboard page, so
severity display, CSV export, and empty states look and behave
consistently everywhere rather than being redone per page.
"""

import streamlit as st

SEVERITY_LABELS = {
    "critical": "🔴 Critical",
    "high": "🟠 High",
    "medium": "🟡 Medium",
    "low": "🟢 Low",
    "unable_to_assess": "⚪ Unable to assess",
    "not_applicable": "⚫ Not applicable",
    "insufficient": "🟠 Insufficient",
    "sufficient": "🟢 Sufficient",
    "cannot_determine": "⚪ Cannot determine",
}


def severity_label(value):
    """Consistent severity display text for any of the risk/readiness
    vocabularies used across the five agents -- never invents a label
    for an unrecognized value."""
    if value is None:
        return "⚪ Unknown"
    return SEVERITY_LABELS.get(value, f"⚪ {value}")


def severity_badge(value):
    st.markdown(f"**{severity_label(value)}**")


def data_freshness_note(note):
    st.caption(f"📅 {note}")


def empty_state(message):
    st.info(message)


def error_state(message):
    """Displays an agent/data error without ever echoing secrets -- the
    underlying agent exceptions in this project never carry API keys or
    personal data, but this stays generic regardless."""
    st.error(f"⚠️ {message}")


def data_gaps_panel(data_gaps):
    if not data_gaps:
        return
    with st.expander(f"⚠️ {len(data_gaps)} data gap(s) / uncertainty note(s)"):
        for gap in data_gaps:
            st.markdown(f"- {gap}")


def csv_download_button(df, label, filename, key=None):
    if df is None or df.empty:
        return
    st.download_button(
        label=f"⬇️ {label}",
        data=df.to_csv(index=False).encode("utf-8"),
        file_name=filename,
        mime="text/csv",
        key=key,
    )


def disclaimer_footer(text=None):
    st.caption(
        text
        or "All recommendations are read-only and require human approval. "
        "No order, inventory, or customer record is modified by this dashboard."
    )
