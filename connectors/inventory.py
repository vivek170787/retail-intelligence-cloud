"""Connector for store/warehouse inventory snapshot (data/inventory.csv)."""

from connectors.base import load_csv

REQUIRED_COLUMNS = [
    "sku", "location_id", "location_type", "on_hand_quantity",
    "reserved_quantity", "available_quantity", "last_updated",
]


def load_inventory():
    """Return the inventory snapshot as a pandas DataFrame."""
    return load_csv(
        "inventory.csv",
        required_columns=REQUIRED_COLUMNS,
        parse_dates=["last_updated"],
    )
