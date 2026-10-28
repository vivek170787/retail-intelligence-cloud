"""Connector for warehouse stock dataset (data/warehouse.csv)."""

from connectors.base import load_csv

REQUIRED_COLUMNS = [
    "warehouse_id", "sku", "on_hand_quantity", "reserved_quantity",
    "inbound_quantity", "supplier_lead_time_days",
]


def load_warehouse():
    """Return warehouse stock as a pandas DataFrame."""
    return load_csv("warehouse.csv", required_columns=REQUIRED_COLUMNS)
