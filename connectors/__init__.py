"""
Data connectors for the eight synthetic retail datasets.

Each module reads one CSV file from data/ using Pandas, resolving the file
path relative to the project root. Missing files or missing required
columns raise clear errors instead of silently fabricating data.
"""

from connectors.products import load_products
from connectors.stores import load_stores
from connectors.pos_sales import load_pos_sales
from connectors.inventory import load_inventory
from connectors.warehouse import load_warehouse
from connectors.orders import load_orders
from connectors.marketplace import load_marketplace
from connectors.promotions import load_promotions

__all__ = [
    "load_products",
    "load_stores",
    "load_pos_sales",
    "load_inventory",
    "load_warehouse",
    "load_orders",
    "load_marketplace",
    "load_promotions",
]
