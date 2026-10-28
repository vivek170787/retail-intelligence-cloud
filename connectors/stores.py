"""Connector for the store master dataset (data/stores.csv)."""

from connectors.base import load_csv

REQUIRED_COLUMNS = ["store_id", "store_name", "city", "region", "store_type"]


def load_stores():
    """Return the store master as a pandas DataFrame."""
    return load_csv("stores.csv", required_columns=REQUIRED_COLUMNS)
