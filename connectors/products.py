"""Connector for the product master dataset (data/products.csv)."""

from connectors.base import load_csv

REQUIRED_COLUMNS = ["sku", "product_name", "category", "brand", "selling_price", "cost_price"]


def load_products():
    """Return the product master as a pandas DataFrame."""
    return load_csv("products.csv", required_columns=REQUIRED_COLUMNS)
