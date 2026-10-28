"""Connector for marketplace listings dataset (data/marketplace.csv)."""

from connectors.base import load_csv

REQUIRED_COLUMNS = [
    "marketplace", "listing_id", "sku", "listing_status",
    "listed_price", "available_quantity",
]


def load_marketplace():
    """Return marketplace listings as a pandas DataFrame."""
    return load_csv("marketplace.csv", required_columns=REQUIRED_COLUMNS)
