"""Connector for promotions calendar dataset (data/promotions.csv)."""

from connectors.base import load_csv

REQUIRED_COLUMNS = [
    "promotion_id", "sku", "promotion_name", "discount_percent",
    "start_date", "end_date", "promotion_channel",
]


def load_promotions():
    """Return promotions as a pandas DataFrame."""
    return load_csv(
        "promotions.csv",
        required_columns=REQUIRED_COLUMNS,
        parse_dates=["start_date", "end_date"],
    )
