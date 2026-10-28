"""
validate_dummy_data.py

Validates the synthetic retail CSV files produced by generate_dummy_data.py
in ./data/. Prints a clear PASS/FAIL report per check and an overall result.

Checks performed:
  - All expected CSV files exist.
  - Each dataset contains at least one record.
  - Required columns are present in each file.
  - SKUs referenced in other datasets exist in products.csv.
  - Store IDs / warehouse IDs referenced elsewhere are valid.
  - All quantity columns are non-negative.
  - available_quantity == on_hand_quantity - reserved_quantity in inventory.csv.
  - Date columns parse as valid dates.
  - Duplicate primary keys are reported.
"""

import os
import sys

import pandas as pd

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

EXPECTED_FILES = {
    "products.csv": {
        "columns": ["sku", "product_name", "category", "brand", "selling_price", "cost_price"],
        "primary_key": "sku",
    },
    "stores.csv": {
        "columns": ["store_id", "store_name", "city", "region", "store_type"],
        "primary_key": "store_id",
    },
    "pos_sales.csv": {
        "columns": ["transaction_id", "transaction_date", "store_id", "sku",
                    "quantity_sold", "selling_price", "sales_channel"],
        "primary_key": "transaction_id",
    },
    "inventory.csv": {
        "columns": ["sku", "location_id", "location_type", "on_hand_quantity",
                    "reserved_quantity", "available_quantity", "last_updated"],
        "primary_key": None,  # composite (sku, location_id)
    },
    "warehouse.csv": {
        "columns": ["warehouse_id", "sku", "on_hand_quantity", "reserved_quantity",
                    "inbound_quantity", "supplier_lead_time_days"],
        "primary_key": None,  # composite (warehouse_id, sku)
    },
    "orders.csv": {
        "columns": ["order_id", "customer_id", "order_date", "sku", "quantity",
                    "order_status", "fulfillment_location", "promised_delivery_date"],
        "primary_key": "order_id",
    },
    "marketplace.csv": {
        "columns": ["marketplace", "listing_id", "sku", "listing_status",
                    "listed_price", "available_quantity"],
        "primary_key": "listing_id",
    },
    "promotions.csv": {
        "columns": ["promotion_id", "sku", "promotion_name", "discount_percent",
                    "start_date", "end_date", "promotion_channel"],
        "primary_key": "promotion_id",
    },
}

DATE_COLUMNS = {
    "pos_sales.csv": ["transaction_date"],
    "inventory.csv": ["last_updated"],
    "orders.csv": ["order_date", "promised_delivery_date"],
    "promotions.csv": ["start_date", "end_date"],
}

QUANTITY_COLUMNS = {
    "pos_sales.csv": ["quantity_sold"],
    "inventory.csv": ["on_hand_quantity", "reserved_quantity", "available_quantity"],
    "warehouse.csv": ["on_hand_quantity", "reserved_quantity", "inbound_quantity"],
    "orders.csv": ["quantity"],
    "marketplace.csv": ["available_quantity"],
}

SKU_REFERENCE_FILES = ["pos_sales.csv", "inventory.csv", "warehouse.csv",
                        "orders.csv", "marketplace.csv", "promotions.csv"]


class Report:
    def __init__(self):
        self.results = []  # list of (check_name, passed: bool, detail: str)

    def add(self, name, passed, detail=""):
        self.results.append((name, passed, detail))

    def print_report(self):
        print("=" * 70)
        print("SYNTHETIC RETAIL DATA VALIDATION REPORT")
        print("=" * 70)
        overall_pass = True
        for name, passed, detail in self.results:
            status = "PASS" if passed else "FAIL"
            if not passed:
                overall_pass = False
            line = f"[{status}] {name}"
            print(line)
            if detail:
                for d_line in detail.splitlines():
                    print(f"       {d_line}")
        print("=" * 70)
        print(f"OVERALL RESULT: {'PASS' if overall_pass else 'FAIL'}")
        print("=" * 70)
        return overall_pass


def load_csv(filename):
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        return None
    try:
        return pd.read_csv(path)
    except Exception as e:
        return str(e)


def main():
    report = Report()
    dfs = {}

    # 1. File existence
    missing_files = []
    for filename in EXPECTED_FILES:
        path = os.path.join(DATA_DIR, filename)
        if os.path.exists(path):
            dfs[filename] = load_csv(filename)
        else:
            missing_files.append(filename)
    report.add(
        "All expected CSV files exist",
        len(missing_files) == 0,
        "" if not missing_files else f"Missing: {missing_files}",
    )

    if missing_files:
        report.print_report()
        sys.exit(1)

    # Guard against parse errors
    parse_errors = {f: df for f, df in dfs.items() if isinstance(df, str)}
    report.add(
        "All CSV files parse correctly",
        len(parse_errors) == 0,
        "" if not parse_errors else "\n".join(f"{f}: {err}" for f, err in parse_errors.items()),
    )
    if parse_errors:
        report.print_report()
        sys.exit(1)

    # 2. Non-empty datasets
    empty_files = [f for f, df in dfs.items() if len(df) == 0]
    report.add(
        "Each dataset contains at least one record",
        len(empty_files) == 0,
        "" if not empty_files else f"Empty files: {empty_files}",
    )

    # 3. Required columns
    missing_cols_report = []
    for filename, spec in EXPECTED_FILES.items():
        df = dfs[filename]
        missing_cols = [c for c in spec["columns"] if c not in df.columns]
        if missing_cols:
            missing_cols_report.append(f"{filename} missing columns: {missing_cols}")
    report.add(
        "Required columns present in each file",
        len(missing_cols_report) == 0,
        "\n".join(missing_cols_report),
    )

    # 4. SKU referential integrity
    products_df = dfs["products.csv"]
    valid_skus = set(products_df["sku"].astype(str))
    sku_issues = []
    for filename in SKU_REFERENCE_FILES:
        df = dfs[filename]
        if "sku" not in df.columns:
            continue
        invalid = set(df["sku"].astype(str)) - valid_skus
        if invalid:
            sku_issues.append(f"{filename} has {len(invalid)} invalid SKU(s): {sorted(invalid)[:10]}")
    report.add(
        "SKUs reference valid products",
        len(sku_issues) == 0,
        "\n".join(sku_issues),
    )

    # 5. Store / warehouse ID validity
    store_ids = set(dfs["stores.csv"]["store_id"].astype(str))
    warehouse_ids = set(dfs["warehouse.csv"]["warehouse_id"].astype(str))
    location_issues = []

    # pos_sales.store_id must be a valid store
    invalid_pos_stores = set(dfs["pos_sales.csv"]["store_id"].astype(str)) - store_ids
    if invalid_pos_stores:
        location_issues.append(f"pos_sales.csv has invalid store_id(s): {sorted(invalid_pos_stores)[:10]}")

    # inventory.location_id must be a valid store or warehouse, consistent with location_type
    inv_df = dfs["inventory.csv"]
    for loc_type, valid_set, label in [("store", store_ids, "store"), ("warehouse", warehouse_ids, "warehouse")]:
        subset = inv_df[inv_df["location_type"] == loc_type]
        invalid_locs = set(subset["location_id"].astype(str)) - valid_set
        if invalid_locs:
            location_issues.append(
                f"inventory.csv has invalid {label} location_id(s): {sorted(invalid_locs)[:10]}"
            )

    # orders.fulfillment_location must be a valid store or warehouse
    valid_fulfillment = store_ids | warehouse_ids
    invalid_fulfillment = set(dfs["orders.csv"]["fulfillment_location"].astype(str)) - valid_fulfillment
    if invalid_fulfillment:
        location_issues.append(
            f"orders.csv has invalid fulfillment_location(s): {sorted(invalid_fulfillment)[:10]}"
        )

    report.add(
        "Store and warehouse IDs are valid",
        len(location_issues) == 0,
        "\n".join(location_issues),
    )

    # 6. Non-negative quantities
    negative_qty_issues = []
    for filename, cols in QUANTITY_COLUMNS.items():
        df = dfs[filename]
        for col in cols:
            if col in df.columns:
                neg_count = (df[col] < 0).sum()
                if neg_count > 0:
                    negative_qty_issues.append(f"{filename}.{col} has {neg_count} negative value(s)")
    report.add(
        "All quantity columns are non-negative",
        len(negative_qty_issues) == 0,
        "\n".join(negative_qty_issues),
    )

    # 7. available_quantity == on_hand_quantity - reserved_quantity (inventory.csv)
    inv_check = inv_df.copy()
    inv_check["expected_available"] = inv_check["on_hand_quantity"] - inv_check["reserved_quantity"]
    mismatches = inv_check[inv_check["available_quantity"] != inv_check["expected_available"]]
    report.add(
        "inventory.csv: available_quantity == on_hand_quantity - reserved_quantity",
        len(mismatches) == 0,
        "" if len(mismatches) == 0 else f"{len(mismatches)} row(s) mismatch, e.g.:\n{mismatches.head(5).to_string(index=False)}",
    )

    # 8. Valid dates
    date_issues = []
    for filename, cols in DATE_COLUMNS.items():
        df = dfs[filename]
        for col in cols:
            if col in df.columns:
                parsed = pd.to_datetime(df[col], errors="coerce", format="%Y-%m-%d")
                bad_count = parsed.isna().sum()
                if bad_count > 0:
                    date_issues.append(f"{filename}.{col} has {bad_count} invalid date value(s)")
    report.add(
        "Date columns contain valid dates",
        len(date_issues) == 0,
        "\n".join(date_issues),
    )

    # 9. Duplicate primary keys
    dup_report = []
    for filename, spec in EXPECTED_FILES.items():
        pk = spec["primary_key"]
        if pk is None:
            continue
        df = dfs[filename]
        dup_count = df[pk].duplicated().sum()
        if dup_count > 0:
            dup_values = df[df[pk].duplicated(keep=False)][pk].unique()[:10]
            dup_report.append(f"{filename} has {dup_count} duplicate '{pk}' value(s): {list(dup_values)}")

    # Composite key checks for inventory.csv (sku, location_id) and warehouse.csv (warehouse_id, sku)
    inv_dup = inv_df.duplicated(subset=["sku", "location_id"]).sum()
    if inv_dup > 0:
        dup_report.append(f"inventory.csv has {inv_dup} duplicate (sku, location_id) combination(s)")

    wh_df = dfs["warehouse.csv"]
    wh_dup = wh_df.duplicated(subset=["warehouse_id", "sku"]).sum()
    if wh_dup > 0:
        dup_report.append(f"warehouse.csv has {wh_dup} duplicate (warehouse_id, sku) combination(s)")

    report.add(
        "No duplicate primary keys",
        len(dup_report) == 0,
        "\n".join(dup_report),
    )

    # 10. Minimum record count sanity checks (per task spec)
    size_issues = []
    if len(dfs["products.csv"]) < 50:
        size_issues.append(f"products.csv has only {len(dfs['products.csv'])} rows (expected >= 50)")
    if len(dfs["stores.csv"]) != 10:
        size_issues.append(f"stores.csv has {len(dfs['stores.csv'])} rows (expected 10)")
    if len(dfs["orders.csv"]) < 500:
        size_issues.append(f"orders.csv has only {len(dfs['orders.csv'])} rows (expected >= 500)")
    report.add(
        "Dataset sizes meet minimum requirements",
        len(size_issues) == 0,
        "\n".join(size_issues),
    )

    overall_pass = report.print_report()
    sys.exit(0 if overall_pass else 1)


if __name__ == "__main__":
    main()
