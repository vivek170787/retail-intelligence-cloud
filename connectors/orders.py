"""Connector for omnichannel orders dataset (data/orders.csv)."""

from connectors.base import load_csv

REQUIRED_COLUMNS = [
    "order_id", "customer_id", "order_date", "sku", "quantity",
    "order_status", "fulfillment_location", "promised_delivery_date",
]


def load_orders():
    """Return orders as a pandas DataFrame."""
    return load_csv(
        "orders.csv",
        required_columns=REQUIRED_COLUMNS,
        parse_dates=["order_date", "promised_delivery_date"],
    )
