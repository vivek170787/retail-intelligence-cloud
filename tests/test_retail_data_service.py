import pandas as pd
import pytest

import connectors.base as base
from services.retail_data_service import RetailDataService


@pytest.fixture
def service():
    return RetailDataService()


def test_get_products(service):
    df = service.get_products()
    assert len(df) > 0
    assert "sku" in df.columns


def test_get_stores(service):
    df = service.get_stores()
    assert len(df) > 0
    assert "store_id" in df.columns


def test_get_inventory_by_sku_known(service):
    sku = service.get_products()["sku"].iloc[0]
    df = service.get_inventory_by_sku(sku)
    assert len(df) > 0
    assert (df["sku"] == sku).all()


def test_get_sales_by_sku_known(service):
    sales = service.get_sales()
    sku = sales["sku"].iloc[0]
    df = service.get_sales_by_sku(sku)
    assert len(df) > 0
    assert (df["sku"] == sku).all()
    assert len(df) == len(sales[sales["sku"] == sku])


def test_get_orders_by_status_known(service):
    orders = service.get_orders()
    status = orders["order_status"].iloc[0]
    df = service.get_orders_by_status(status)
    assert len(df) > 0
    assert (df["order_status"] == status).all()
    assert len(df) == len(orders[orders["order_status"] == status])


def test_get_orders_by_sku_known(service):
    orders = service.get_orders()
    sku = orders["sku"].iloc[0]
    df = service.get_orders_by_sku(sku)
    assert len(df) > 0
    assert (df["sku"] == sku).all()


def test_get_warehouse_stock_known(service):
    sku = service.get_products()["sku"].iloc[0]
    df = service.get_warehouse_stock(sku)
    assert len(df) > 0
    assert (df["sku"] == sku).all()


def test_unknown_sku_returns_empty_dataframe(service):
    df = service.get_inventory_by_sku("SKU-DOES-NOT-EXIST-0000")
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 0


def test_unknown_sku_for_sales_returns_empty_dataframe(service):
    df = service.get_sales_by_sku("SKU-DOES-NOT-EXIST-0000")
    assert len(df) == 0


def test_invalid_sku_type_raises(service):
    with pytest.raises(ValueError):
        service.get_inventory_by_sku("")
    with pytest.raises(ValueError):
        service.get_inventory_by_sku(None)


def test_invalid_status_type_raises(service):
    with pytest.raises(ValueError):
        service.get_orders_by_status("")


def test_missing_csv_file_propagates_clear_error(tmp_path, monkeypatch):
    monkeypatch.setattr(base, "DATA_DIR", tmp_path)
    service = RetailDataService()

    with pytest.raises(FileNotFoundError) as exc_info:
        service.get_orders()

    assert "orders.csv" in str(exc_info.value)


def test_cache_is_reused_across_calls(service):
    first = service.get_products()
    second = service.get_products()
    assert first is second  # same cached object, not re-read from disk
