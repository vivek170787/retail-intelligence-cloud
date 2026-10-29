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


_ACRONYMS = {"sku": "SKU", "skus": "SKUs", "id": "ID", "ids": "IDs", "cx": "Customer Experience"}
_ITEM_LABEL_KEYS = ("sku", "order_id", "store_id", "promotion_id", "name", "id")


def _humanize_key(key):
    parts = str(key).split("_")
    return " ".join(_ACRONYMS.get(p.lower(), p.capitalize()) for p in parts)


def _format_scalar(value):
    if value is None:
        return "_not available_"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, (int, float)):
        return f"{value:,}"
    return str(value)


def _item_label(item, index):
    for key in _ITEM_LABEL_KEYS:
        if item.get(key):
            return str(item[key])
    return f"Entry {index + 1}"


def _render_evidence(value, indent=0):
    """Recursively turns an arbitrary (and per-agent differently-shaped)
    evidence value into plain-English nested bullet lines -- humanizing
    every field name and formatting every value, but never inventing or
    recomputing a number that wasn't already in the evidence."""
    pad = "    " * indent

    if isinstance(value, dict):
        if not value:
            return [f"{pad}- _no details recorded_"]
        lines = []
        for key, val in value.items():
            label = f"**{_humanize_key(key)}:**"
            if (isinstance(val, dict) and val) or (isinstance(val, list) and any(isinstance(i, (dict, list)) for i in val)):
                lines.append(f"{pad}- {label}")
                lines.extend(_render_evidence(val, indent + 1))
            elif isinstance(val, list):
                joined = ", ".join(_format_scalar(item) for item in val) if val else "_none_"
                lines.append(f"{pad}- {label} {joined}")
            else:
                lines.append(f"{pad}- {label} {_format_scalar(val)}")
        return lines

    if isinstance(value, list):
        if not value:
            return [f"{pad}- _none_"]
        lines = []
        for i, item in enumerate(value):
            if isinstance(item, dict):
                lines.append(f"{pad}- **{_item_label(item, i)}:**")
                lines.extend(_render_evidence(item, indent + 1))
            elif isinstance(item, list):
                lines.append(f"{pad}- Entry {i + 1}:")
                lines.extend(_render_evidence(item, indent + 1))
            else:
                lines.append(f"{pad}- {_format_scalar(item)}")
        return lines

    return [f"{pad}- {_format_scalar(value)}"]


def render_evidence(evidence):
    """Renders the orchestrator/agent evidence dict in plain English
    (humanized field names, formatted values) instead of a raw JSON
    dump -- same data, readable instead of code. Does not open its own
    expander, so it is safe to call inside a caller's own expander
    (Streamlit does not allow nested expanders)."""
    if not evidence:
        st.caption("No supporting evidence was recorded for this result.")
        return
    st.markdown("\n".join(_render_evidence(evidence)))


def evidence_panel(evidence, title="Supporting evidence"):
    """Convenience wrapper that puts render_evidence inside its own
    expander. Do not call this from inside another expander -- call
    render_evidence directly there instead."""
    with st.expander(title):
        render_evidence(evidence)
