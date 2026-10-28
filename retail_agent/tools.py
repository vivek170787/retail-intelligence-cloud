"""
Agent tool wrappers around RetailDataService.

Each RetailDataService method gets a plain, directly-testable "_impl"
function containing all real logic (service call, DataFrame-safety,
JSON-safe serialization, input-error handling), plus a thin
@function_tool-decorated public wrapper that the Agent actually calls.

The _impl/wrapper split exists because @function_tool wraps a function into
a non-callable FunctionTool object (confirmed: calling it directly raises
"'FunctionTool' object is not callable"), so tests must exercise the _impl
functions to avoid depending on the Agents SDK or making any network call.

Only ValueError raised by RetailDataService's own sku/status validation is
caught here and turned into a model-visible error string. FileNotFoundError
and column-validation ValueErrors from the connectors (i.e. a broken data
layer) are allowed to propagate uncaught -- those are real infrastructure
failures, not model-correctable input errors, and must not be silently
swallowed or faked into an empty result.
"""

import numpy as np
import pandas as pd
from agents import function_tool

from services.retail_data_service import RetailDataService

_service = RetailDataService()

_SERVICE_VALUE_ERROR_PREFIX = "Invalid input"


def _df_to_records(df: pd.DataFrame) -> list[dict]:
    """
    Convert a DataFrame to a list of plain, JSON-safe dicts.

    Converts pandas/numpy scalar types (Timestamp, NaT, int64, float64, NaN)
    to native Python types (str/int/float/None). Never mutates the input
    DataFrame -- RetailDataService's "get all" methods return the same
    cached object on every call, so in-place changes here would corrupt
    the shared cache for every other caller.
    """
    safe = df.copy()
    for col in safe.columns:
        if pd.api.types.is_datetime64_any_dtype(safe[col]):
            safe[col] = safe[col].dt.strftime("%Y-%m-%d")

    records = safe.to_dict(orient="records")

    # pandas' .where(cond, None) normalizes None back to float NaN for
    # already-missing cells, so missing values are swept explicitly here
    # instead, alongside converting numpy scalar types to native Python ones.
    for row in records:
        for key, value in row.items():
            if isinstance(value, np.integer):
                value = int(value)
            elif isinstance(value, np.floating):
                value = float(value)
            if value is not None:
                try:
                    if pd.isna(value):
                        value = None
                except (TypeError, ValueError):
                    pass
            row[key] = value
    return records


def _paginate(df: pd.DataFrame, limit: int) -> dict:
    """Wrap an unbounded dataset with a total/returned count so the model
    always knows whether it is seeing the full dataset or a partial sample."""
    total_rows = len(df)
    limited = df.head(limit)
    return {
        "total_rows": total_rows,
        "returned_rows": len(limited),
        "records": _df_to_records(limited),
    }


# --------------------------------------------------------------------- #
# Product master
# --------------------------------------------------------------------- #
def _get_products_impl() -> list[dict]:
    return _df_to_records(_service.get_products())


@function_tool
def get_products() -> list[dict]:
    """Get the full product master catalog (SKU, name, category, brand,
    selling price, cost price) for every product in the system."""
    return _get_products_impl()


# --------------------------------------------------------------------- #
# Store master
# --------------------------------------------------------------------- #
def _get_stores_impl() -> list[dict]:
    return _df_to_records(_service.get_stores())


@function_tool
def get_stores() -> list[dict]:
    """Get the full store master list (store ID, name, city, region,
    store type) for every retail store in the system."""
    return _get_stores_impl()


# --------------------------------------------------------------------- #
# POS sales
# --------------------------------------------------------------------- #
def _get_sales_impl(limit: int = 100) -> dict:
    return _paginate(_service.get_sales(), limit)


@function_tool
def get_sales(limit: int = 100) -> dict:
    """Get recent POS sales transactions across all stores and channels.

    This dataset can contain thousands of rows, so results are capped at
    `limit`. The response includes total_rows (the true total available)
    and returned_rows, so you know whether you are seeing everything or a
    partial sample.

    Args:
        limit: Maximum number of transaction records to return.
    """
    return _get_sales_impl(limit)


def _get_sales_by_sku_impl(sku) -> list[dict] | str:
    try:
        df = _service.get_sales_by_sku(sku)
    except ValueError as exc:
        return f"{_SERVICE_VALUE_ERROR_PREFIX}: {exc}"
    return _df_to_records(df)


@function_tool
def get_sales_by_sku(sku: str) -> list[dict] | str:
    """Get all POS sales transactions for a single SKU.

    Args:
        sku: The product SKU to look up. Must be a non-empty string. A
            real but currently-unsold SKU returns an empty list, which is
            a normal result, not an error.
    """
    return _get_sales_by_sku_impl(sku)


# --------------------------------------------------------------------- #
# Inventory
# --------------------------------------------------------------------- #
def _get_inventory_impl(limit: int = 100) -> dict:
    return _paginate(_service.get_inventory(), limit)


@function_tool
def get_inventory(limit: int = 100) -> dict:
    """Get current inventory snapshot rows across all stores and
    warehouses (one row per SKU per location).

    This dataset can contain hundreds of rows, so results are capped at
    `limit`. The response includes total_rows (the true total available)
    and returned_rows, so you know whether you are seeing everything or a
    partial sample.

    Args:
        limit: Maximum number of inventory records to return.
    """
    return _get_inventory_impl(limit)


def _get_inventory_by_sku_impl(sku) -> list[dict] | str:
    try:
        df = _service.get_inventory_by_sku(sku)
    except ValueError as exc:
        return f"{_SERVICE_VALUE_ERROR_PREFIX}: {exc}"
    return _df_to_records(df)


@function_tool
def get_inventory_by_sku(sku: str) -> list[dict] | str:
    """Get current inventory records (store + warehouse) for a single SKU.

    Args:
        sku: The product SKU to look up. Must be a non-empty string. An
            unknown-but-valid SKU returns an empty list, not an error.
    """
    return _get_inventory_by_sku_impl(sku)


# --------------------------------------------------------------------- #
# Warehouse
# --------------------------------------------------------------------- #
def _get_warehouse_stock_impl(sku) -> list[dict] | str:
    try:
        df = _service.get_warehouse_stock(sku)
    except ValueError as exc:
        return f"{_SERVICE_VALUE_ERROR_PREFIX}: {exc}"
    return _df_to_records(df)


@function_tool
def get_warehouse_stock(sku: str) -> list[dict] | str:
    """Get warehouse stock records (on-hand, reserved, inbound, supplier
    lead time) for a single SKU across all warehouses.

    Args:
        sku: The product SKU to look up. Must be a non-empty string. An
            unknown-but-valid SKU returns an empty list, not an error.
    """
    return _get_warehouse_stock_impl(sku)


# --------------------------------------------------------------------- #
# Orders
# --------------------------------------------------------------------- #
def _get_orders_impl(limit: int = 100) -> dict:
    return _paginate(_service.get_orders(), limit)


@function_tool
def get_orders(limit: int = 100) -> dict:
    """Get recent omnichannel orders across all customers and fulfillment
    locations.

    This dataset can contain hundreds of rows, so results are capped at
    `limit`. The response includes total_rows (the true total available)
    and returned_rows, so you know whether you are seeing everything or a
    partial sample.

    Args:
        limit: Maximum number of order records to return.
    """
    return _get_orders_impl(limit)


def _get_orders_by_status_impl(status) -> list[dict] | str:
    try:
        df = _service.get_orders_by_status(status)
    except ValueError as exc:
        return f"{_SERVICE_VALUE_ERROR_PREFIX}: {exc}"
    return _df_to_records(df)


@function_tool
def get_orders_by_status(status: str) -> list[dict] | str:
    """Get all orders with a given order status (case-insensitive).

    Args:
        status: Order status to filter by, e.g. "PLACED", "PROCESSING",
            "SHIPPED", "DELIVERED", or "CANCELLED". Must be a non-empty
            string. A valid but unused status returns an empty list, not
            an error.
    """
    return _get_orders_by_status_impl(status)


def _get_orders_by_sku_impl(sku) -> list[dict] | str:
    try:
        df = _service.get_orders_by_sku(sku)
    except ValueError as exc:
        return f"{_SERVICE_VALUE_ERROR_PREFIX}: {exc}"
    return _df_to_records(df)


@function_tool
def get_orders_by_sku(sku: str) -> list[dict] | str:
    """Get all orders that include a given SKU.

    Args:
        sku: The product SKU to look up. Must be a non-empty string. A
            real but never-ordered SKU returns an empty list, not an error.
    """
    return _get_orders_by_sku_impl(sku)


# --------------------------------------------------------------------- #
# Marketplace
# --------------------------------------------------------------------- #
def _get_marketplace_listings_impl(sku) -> list[dict] | str:
    try:
        df = _service.get_marketplace_listings(sku)
    except ValueError as exc:
        return f"{_SERVICE_VALUE_ERROR_PREFIX}: {exc}"
    return _df_to_records(df)


@function_tool
def get_marketplace_listings(sku: str) -> list[dict] | str:
    """Get marketplace listings (Amazon, Flipkart, RetailerWebsite) for a
    single SKU.

    Args:
        sku: The product SKU to look up. Must be a non-empty string. A
            real SKU with no marketplace listings returns an empty list,
            not an error.
    """
    return _get_marketplace_listings_impl(sku)


# --------------------------------------------------------------------- #
# Promotions
# --------------------------------------------------------------------- #
def _get_promotions_impl(sku) -> list[dict] | str:
    try:
        df = _service.get_promotions(sku)
    except ValueError as exc:
        return f"{_SERVICE_VALUE_ERROR_PREFIX}: {exc}"
    return _df_to_records(df)


@function_tool
def get_promotions(sku: str) -> list[dict] | str:
    """Get promotion calendar entries for a single SKU.

    Args:
        sku: The product SKU to look up. Must be a non-empty string. A
            real SKU with no active or scheduled promotions returns an
            empty list, not an error.
    """
    return _get_promotions_impl(sku)
