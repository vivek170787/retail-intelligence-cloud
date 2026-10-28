"""
Tests for retail_agent/tools.py.

These exercise the plain "_impl" functions directly -- no OpenAI API key,
no network call, no Agents SDK runner involved. @function_tool wraps a
function into a non-callable FunctionTool object, so the _impl functions
are the only part of tools.py that can be unit tested without the SDK.
"""

import pandas as pd
import pytest

from retail_agent.tools import (
    _df_to_records,
    _get_products_impl,
    _get_stores_impl,
    _get_sales_impl,
    _get_sales_by_sku_impl,
    _get_inventory_impl,
    _get_inventory_by_sku_impl,
    _get_warehouse_stock_impl,
    _get_orders_impl,
    _get_orders_by_status_impl,
    _get_orders_by_sku_impl,
    _get_marketplace_listings_impl,
    _get_promotions_impl,
    _service,
)


def test_get_products_impl_returns_list_of_dicts():
    records = _get_products_impl()
    assert isinstance(records, list)
    assert len(records) > 0
    assert "sku" in records[0]


def test_get_stores_impl_returns_list_of_dicts():
    records = _get_stores_impl()
    assert isinstance(records, list)
    assert len(records) > 0
    assert "store_id" in records[0]


def test_get_inventory_by_sku_known_sku():
    sku = _get_products_impl()[0]["sku"]
    records = _get_inventory_by_sku_impl(sku)
    assert isinstance(records, list)
    assert len(records) > 0
    assert all(r["sku"] == sku for r in records)


def test_get_inventory_by_sku_unknown_sku_returns_empty_not_error():
    records = _get_inventory_by_sku_impl("NOT-A-REAL-SKU-0000")
    assert records == []


def test_get_inventory_by_sku_invalid_input_returns_error_string():
    result = _get_inventory_by_sku_impl(None)
    assert isinstance(result, str)
    assert "Invalid input" in result

    result = _get_inventory_by_sku_impl("")
    assert isinstance(result, str)
    assert "Invalid input" in result


def test_get_sales_by_sku_known_sku():
    sales = _service.get_sales()
    sku = sales["sku"].iloc[0]
    records = _get_sales_by_sku_impl(sku)
    assert isinstance(records, list)
    assert len(records) > 0
    assert all(r["sku"] == sku for r in records)


def test_get_sales_by_sku_invalid_input_returns_error_string():
    result = _get_sales_by_sku_impl(123)
    assert isinstance(result, str)
    assert "Invalid input" in result


def test_get_warehouse_stock_known_sku():
    sku = _get_products_impl()[0]["sku"]
    records = _get_warehouse_stock_impl(sku)
    assert isinstance(records, list)
    assert len(records) > 0
    assert all(r["sku"] == sku for r in records)


def test_get_orders_by_status_known_status():
    orders = _service.get_orders()
    status = orders["order_status"].iloc[0]
    records = _get_orders_by_status_impl(status)
    assert isinstance(records, list)
    assert len(records) > 0
    assert all(r["order_status"] == status for r in records)


def test_get_orders_by_status_invalid_input_returns_error_string():
    result = _get_orders_by_status_impl("")
    assert isinstance(result, str)
    assert "Invalid input" in result


def test_get_orders_by_sku_known_sku():
    orders = _service.get_orders()
    sku = orders["sku"].iloc[0]
    records = _get_orders_by_sku_impl(sku)
    assert isinstance(records, list)
    assert len(records) > 0
    assert all(r["sku"] == sku for r in records)


def test_get_marketplace_listings_unknown_sku_returns_empty():
    records = _get_marketplace_listings_impl("NOT-A-REAL-SKU-0000")
    assert records == []


def test_get_promotions_unknown_sku_returns_empty():
    records = _get_promotions_impl("NOT-A-REAL-SKU-0000")
    assert records == []


def test_get_sales_impl_paginates_with_total_and_returned_counts():
    result = _get_sales_impl(limit=5)
    assert isinstance(result, dict)
    assert set(result.keys()) == {"total_rows", "returned_rows", "records"}
    assert result["returned_rows"] == 5
    assert result["total_rows"] >= result["returned_rows"]
    assert len(result["records"]) == 5


def test_get_inventory_impl_paginates():
    result = _get_inventory_impl(limit=10)
    assert result["returned_rows"] == min(10, result["total_rows"])
    assert len(result["records"]) == result["returned_rows"]


def test_get_orders_impl_paginates():
    result = _get_orders_impl(limit=10)
    assert result["returned_rows"] == min(10, result["total_rows"])
    assert len(result["records"]) == result["returned_rows"]


def test_df_to_records_converts_dates_and_nans_to_json_safe_values():
    df = pd.DataFrame(
        {
            "a_date": pd.to_datetime(["2026-01-01", None]),
            "a_number": [1.5, float("nan")],
        }
    )
    records = _df_to_records(df)
    assert records[0]["a_date"] == "2026-01-01"
    assert records[1]["a_date"] is None
    assert records[1]["a_number"] is None
    for row in records:
        for value in row.values():
            assert not isinstance(value, pd.Timestamp)


def test_tool_calls_do_not_mutate_shared_cached_dataframe():
    before = _service.get_products()
    before_shape = before.shape
    before_columns = list(before.columns)

    _get_products_impl()
    _get_products_impl()

    after = _service.get_products()
    assert after.shape == before_shape
    assert list(after.columns) == before_columns
    assert after is before  # same cached object identity, untouched
