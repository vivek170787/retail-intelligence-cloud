"""
quality_checks.py

Data quality checks for the retail data integration layer, run against the
datasets as loaded through the connectors (i.e. after schema validation has
already passed).

Checks:
  - Required files and columns exist (implicit: connectors load successfully).
  - Product SKUs are consistent across all datasets that reference a SKU.
  - Store IDs referenced elsewhere are valid.
  - Quantity columns are non-negative.
  - Duplicate primary/composite keys are reported.
  - Missing (NaN) values are reported per column.
  - The number of records loaded per dataset is displayed.

Usage:
    python quality_checks.py
"""

import sys

from connectors.products import load_products
from connectors.stores import load_stores
from connectors.pos_sales import load_pos_sales
from connectors.inventory import load_inventory
from connectors.warehouse import load_warehouse
from connectors.orders import load_orders
from connectors.marketplace import load_marketplace
from connectors.promotions import load_promotions

QUANTITY_COLUMNS = {
    "pos_sales": ["quantity_sold"],
    "inventory": ["on_hand_quantity", "reserved_quantity", "available_quantity"],
    "warehouse": ["on_hand_quantity", "reserved_quantity", "inbound_quantity"],
    "orders": ["quantity"],
    "marketplace": ["available_quantity"],
}

DUPLICATE_KEYS = {
    "products": ["sku"],
    "stores": ["store_id"],
    "pos_sales": ["transaction_id"],
    "orders": ["order_id"],
    "marketplace": ["listing_id"],
    "promotions": ["promotion_id"],
    "inventory": ["sku", "location_id"],
    "warehouse": ["warehouse_id", "sku"],
}


def run_quality_checks(verbose=True):
    """
    Load all eight datasets via the connectors and run data quality checks.

    Returns (passed: bool, report_lines: list[str]).
    """
    lines = []
    passed = True

    def emit(status, message):
        nonlocal passed
        if status == "FAIL":
            passed = False
        lines.append(f"[{status}] {message}")

    # 1. Required files / columns exist (connectors validate this on load).
    try:
        datasets = {
            "products": load_products(),
            "stores": load_stores(),
            "pos_sales": load_pos_sales(),
            "inventory": load_inventory(),
            "warehouse": load_warehouse(),
            "orders": load_orders(),
            "marketplace": load_marketplace(),
            "promotions": load_promotions(),
        }
        emit("PASS", "All required files and columns exist")
    except (FileNotFoundError, ValueError) as exc:
        emit("FAIL", f"Failed to load one or more datasets: {exc}")
        if verbose:
            print("\n".join(lines))
        return passed, lines

    # 2. Record counts
    for name, df in datasets.items():
        lines.append(f"[INFO] {name}: {len(df)} record(s) loaded")

    # 3. SKU consistency
    valid_skus = set(datasets["products"]["sku"].astype(str))
    for name in ["pos_sales", "inventory", "warehouse", "orders", "marketplace", "promotions"]:
        df = datasets[name]
        invalid = set(df["sku"].astype(str)) - valid_skus
        if invalid:
            emit("FAIL", f"{name}: {len(invalid)} SKU(s) not found in products: {sorted(invalid)[:10]}")
        else:
            emit("PASS", f"{name}: all SKUs are consistent with products")

    # 4. Store ID validity
    valid_store_ids = set(datasets["stores"]["store_id"].astype(str))
    valid_warehouse_ids = set(datasets["warehouse"]["warehouse_id"].astype(str))

    invalid_pos_stores = set(datasets["pos_sales"]["store_id"].astype(str)) - valid_store_ids
    if invalid_pos_stores:
        emit("FAIL", f"pos_sales: invalid store_id(s): {sorted(invalid_pos_stores)[:10]}")
    else:
        emit("PASS", "pos_sales: all store_id values are valid")

    inv_df = datasets["inventory"]
    store_rows = inv_df[inv_df["location_type"] == "store"]
    invalid_inv_stores = set(store_rows["location_id"].astype(str)) - valid_store_ids
    if invalid_inv_stores:
        emit("FAIL", f"inventory: invalid store location_id(s): {sorted(invalid_inv_stores)[:10]}")
    else:
        emit("PASS", "inventory: all store location_id values are valid")

    valid_fulfillment = valid_store_ids | valid_warehouse_ids
    invalid_fulfillment = set(datasets["orders"]["fulfillment_location"].astype(str)) - valid_fulfillment
    if invalid_fulfillment:
        emit("FAIL", f"orders: invalid fulfillment_location(s): {sorted(invalid_fulfillment)[:10]}")
    else:
        emit("PASS", "orders: all fulfillment_location values are valid")

    # 5. Non-negative quantities
    for name, cols in QUANTITY_COLUMNS.items():
        df = datasets[name]
        for col in cols:
            neg_count = int((df[col] < 0).sum())
            if neg_count > 0:
                emit("FAIL", f"{name}.{col}: {neg_count} negative value(s)")
            else:
                emit("PASS", f"{name}.{col}: all values non-negative")

    # 6. Duplicate keys
    for name, key_cols in DUPLICATE_KEYS.items():
        df = datasets[name]
        dup_count = int(df.duplicated(subset=key_cols).sum())
        if dup_count > 0:
            emit("FAIL", f"{name}: {dup_count} duplicate record(s) on key {key_cols}")
        else:
            emit("PASS", f"{name}: no duplicate keys on {key_cols}")

    # 7. Missing values
    any_missing = False
    for name, df in datasets.items():
        na_counts = df.isna().sum()
        na_cols = na_counts[na_counts > 0]
        if len(na_cols) > 0:
            any_missing = True
            emit("FAIL", f"{name}: missing values -> {na_cols.to_dict()}")
    if not any_missing:
        emit("PASS", "No missing values found in any dataset")

    if verbose:
        print("\n".join(lines))
        print(f"\nQUALITY CHECKS: {'PASS' if passed else 'FAIL'}")

    return passed, lines


if __name__ == "__main__":
    ok, _ = run_quality_checks(verbose=True)
    sys.exit(0 if ok else 1)
