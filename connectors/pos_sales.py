"""Connector for POS sales transactions (data/pos_sales.csv)."""

from connectors.base import load_csv

REQUIRED_COLUMNS = [
    "transaction_id", "transaction_date", "store_id", "sku",
    "quantity_sold", "selling_price", "sales_channel",
]


def load_pos_sales():
    """Return POS sales transactions as a pandas DataFrame."""
    return load_csv(
        "pos_sales.csv",
        required_columns=REQUIRED_COLUMNS,
        parse_dates=["transaction_date"],
    )
