"""
RetailDataService: a common data access layer over the eight synthetic
retail connectors (products, stores, POS sales, inventory, warehouse,
orders, marketplace, promotions).

Each dataset is lazily loaded once via its connector and cached in memory
for the lifetime of the service instance. Loading errors from the
connectors (missing file, missing column) propagate unchanged so callers
see a clear, specific error rather than a silently empty result.

Unknown-but-well-formed lookup keys (e.g. a SKU that does not exist) return
an empty DataFrame rather than raising, since "no matching records" is a
normal, expected outcome of a query.
"""

from connectors.products import load_products
from connectors.stores import load_stores
from connectors.pos_sales import load_pos_sales
from connectors.inventory import load_inventory
from connectors.warehouse import load_warehouse
from connectors.orders import load_orders
from connectors.marketplace import load_marketplace
from connectors.promotions import load_promotions


class RetailDataService:
    def __init__(self):
        self._cache = {}

    def clear_cache(self):
        """Drop all cached datasets so the next access re-reads from CSV."""
        self._cache.clear()

    def _cached(self, key, loader):
        if key not in self._cache:
            self._cache[key] = loader()
        return self._cache[key]

    @staticmethod
    def _validate_sku(sku):
        if not isinstance(sku, str) or not sku.strip():
            raise ValueError(f"sku must be a non-empty string, got: {sku!r}")
        return sku.strip()

    @staticmethod
    def _validate_status(status):
        if not isinstance(status, str) or not status.strip():
            raise ValueError(f"status must be a non-empty string, got: {status!r}")
        return status.strip()

    # ------------------------------------------------------------------ #
    # Product master
    # ------------------------------------------------------------------ #
    def get_products(self):
        return self._cached("products", load_products)

    # ------------------------------------------------------------------ #
    # Store master
    # ------------------------------------------------------------------ #
    def get_stores(self):
        return self._cached("stores", load_stores)

    # ------------------------------------------------------------------ #
    # POS sales
    # ------------------------------------------------------------------ #
    def get_sales(self):
        return self._cached("sales", load_pos_sales)

    def get_sales_by_sku(self, sku):
        sku = self._validate_sku(sku)
        df = self.get_sales()
        return df[df["sku"] == sku].reset_index(drop=True)

    # ------------------------------------------------------------------ #
    # Inventory
    # ------------------------------------------------------------------ #
    def get_inventory(self):
        return self._cached("inventory", load_inventory)

    def get_inventory_by_sku(self, sku):
        sku = self._validate_sku(sku)
        df = self.get_inventory()
        return df[df["sku"] == sku].reset_index(drop=True)

    # ------------------------------------------------------------------ #
    # Warehouse
    # ------------------------------------------------------------------ #
    def get_warehouse_stock(self, sku=None):
        """Return warehouse stock for one SKU, or the full warehouse table
        when sku is omitted -- same optional-sku/bulk-accessor pattern as
        get_promotions(), added so callers that need every SKU (e.g. the
        Data Quality / Data Sources admin workspaces) reuse this service's
        cache instead of re-reading warehouse.csv via the connector
        directly. Every existing caller already passes sku explicitly."""
        df = self._cached("warehouse", load_warehouse)
        if sku is None:
            return df
        sku = self._validate_sku(sku)
        return df[df["sku"] == sku].reset_index(drop=True)

    # ------------------------------------------------------------------ #
    # Orders
    # ------------------------------------------------------------------ #
    def get_orders(self):
        return self._cached("orders", load_orders)

    def get_orders_by_status(self, status):
        status = self._validate_status(status)
        df = self.get_orders()
        return df[df["order_status"].str.upper() == status.upper()].reset_index(drop=True)

    def get_orders_by_sku(self, sku):
        sku = self._validate_sku(sku)
        df = self.get_orders()
        return df[df["sku"] == sku].reset_index(drop=True)

    # ------------------------------------------------------------------ #
    # Marketplace
    # ------------------------------------------------------------------ #
    def get_marketplace_listings(self, sku=None):
        """Return marketplace listings for one SKU, or the full marketplace
        table when sku is omitted -- same optional-sku/bulk-accessor
        pattern as get_promotions(). Every existing caller already passes
        sku explicitly."""
        df = self._cached("marketplace", load_marketplace)
        if sku is None:
            return df
        sku = self._validate_sku(sku)
        return df[df["sku"] == sku].reset_index(drop=True)

    # ------------------------------------------------------------------ #
    # Promotions
    # ------------------------------------------------------------------ #
    def get_promotions(self, sku=None):
        """Return promotions for one SKU, or the full promotions table
        when sku is omitted (unlike get_sales()/get_orders(), this dataset
        had no bulk "get all" accessor before; adding one here as an
        optional, backward-compatible default rather than a new method,
        since every existing caller already passes sku explicitly)."""
        df = self._cached("promotions", load_promotions)
        if sku is None:
            return df
        sku = self._validate_sku(sku)
        return df[df["sku"] == sku].reset_index(drop=True)
