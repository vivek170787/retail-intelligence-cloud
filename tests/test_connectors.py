import pytest

import connectors.base as base
from connectors.products import load_products
from connectors.stores import load_stores
from connectors.pos_sales import load_pos_sales
from connectors.inventory import load_inventory
from connectors.warehouse import load_warehouse
from connectors.orders import load_orders
from connectors.marketplace import load_marketplace
from connectors.promotions import load_promotions


@pytest.mark.parametrize(
    "loader, required_columns",
    [
        (load_products, ["sku", "product_name", "category", "brand", "selling_price", "cost_price"]),
        (load_stores, ["store_id", "store_name", "city", "region", "store_type"]),
        (load_pos_sales, ["transaction_id", "transaction_date", "store_id", "sku",
                           "quantity_sold", "selling_price", "sales_channel"]),
        (load_inventory, ["sku", "location_id", "location_type", "on_hand_quantity",
                           "reserved_quantity", "available_quantity", "last_updated"]),
        (load_warehouse, ["warehouse_id", "sku", "on_hand_quantity", "reserved_quantity",
                           "inbound_quantity", "supplier_lead_time_days"]),
        (load_orders, ["order_id", "customer_id", "order_date", "sku", "quantity",
                        "order_status", "fulfillment_location", "promised_delivery_date"]),
        (load_marketplace, ["marketplace", "listing_id", "sku", "listing_status",
                             "listed_price", "available_quantity"]),
        (load_promotions, ["promotion_id", "sku", "promotion_name", "discount_percent",
                            "start_date", "end_date", "promotion_channel"]),
    ],
)
def test_connector_loads_nonempty_dataframe_with_required_columns(loader, required_columns):
    df = loader()
    assert len(df) > 0
    for col in required_columns:
        assert col in df.columns


def test_missing_csv_file_raises_clear_error(tmp_path, monkeypatch):
    # Point DATA_DIR at an empty temp directory so products.csv is "missing".
    monkeypatch.setattr(base, "DATA_DIR", tmp_path)

    with pytest.raises(FileNotFoundError) as exc_info:
        load_products()

    message = str(exc_info.value)
    assert "products.csv" in message
    assert "generate_dummy_data.py" in message


def test_missing_required_column_raises_clear_error(tmp_path, monkeypatch):
    # Write a products.csv that is missing the 'cost_price' column.
    bad_csv = tmp_path / "products.csv"
    bad_csv.write_text("sku,product_name,category,brand,selling_price\nSKU-X,Widget,Home,Acme,100\n")
    monkeypatch.setattr(base, "DATA_DIR", tmp_path)

    with pytest.raises(ValueError) as exc_info:
        load_products()

    assert "cost_price" in str(exc_info.value)
