"""
Structured data quality report for the Data Quality workspace.

Runs the SAME checks as quality_checks.py (SKU consistency, store ID
validity, non-negative quantities, duplicate keys, missing values) against
the same eight datasets, but returns a structured dict instead of
printable text lines, and adds data freshness -- the most recent date
value in the three datasets that actually carry a date column
(pos_sales.transaction_date, orders.order_date, inventory.last_updated).
Freshness is never computed for a dataset that has no date column; those
are reported as "not tracked", never guessed.

This module does not modify or duplicate quality_checks.py's own checks by
importing them -- it recomputes the same logic directly, so
quality_checks.py's existing CLI/return contract is left completely
untouched. Every number here still comes directly from the current
contents of data/*.csv -- nothing is sampled or fabricated -- but datasets
are read through RetailDataService's existing in-memory cache (the same
shared service instance api/dependencies.py already hands every router)
rather than re-reading every CSV file from disk on each call to this
report. A fresh RetailDataService() is only constructed as a last-resort
default for standalone/CLI callers that don't already have one.
"""

import pandas as pd

from services.retail_data_service import RetailDataService

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

# Only these three datasets carry a column that genuinely represents when
# the record was last observed/transacted -- every other dataset (products,
# stores, warehouse, marketplace, promotions) has no such column, so
# freshness is reported as "not tracked" for them rather than guessed.
FRESHNESS_DATE_COLUMNS = {
    "pos_sales": "transaction_date",
    "orders": "order_date",
    "inventory": "last_updated",
}


def _load_all_datasets(service):
    return {
        "products": service.get_products(),
        "stores": service.get_stores(),
        "pos_sales": service.get_sales(),
        "inventory": service.get_inventory(),
        "warehouse": service.get_warehouse_stock(),
        "orders": service.get_orders(),
        "marketplace": service.get_marketplace_listings(),
        "promotions": service.get_promotions(),
    }


def _dataset_summaries(datasets):
    summaries = []
    for name, df in datasets.items():
        na_counts = df.isna().sum()
        missing = {col: int(count) for col, count in na_counts.items() if count > 0}
        dup_keys = DUPLICATE_KEYS.get(name)
        dup_count = int(df.duplicated(subset=dup_keys).sum()) if dup_keys else None
        summaries.append({
            "name": name,
            "record_count": int(len(df)),
            "missing_value_counts": missing,
            "duplicate_key_columns": dup_keys,
            "duplicate_record_count": dup_count,
        })
    return summaries


def _validation_checks(datasets):
    checks = []
    valid_skus = set(datasets["products"]["sku"].astype(str))
    for name in ["pos_sales", "inventory", "warehouse", "orders", "marketplace", "promotions"]:
        invalid = sorted(set(datasets[name]["sku"].astype(str)) - valid_skus)
        checks.append({
            "check": f"{name}: sku references exist in products",
            "passed": len(invalid) == 0,
            "invalid_count": len(invalid),
            "examples": invalid[:10],
        })

    valid_store_ids = set(datasets["stores"]["store_id"].astype(str))
    valid_warehouse_ids = set(datasets["warehouse"]["warehouse_id"].astype(str))

    invalid_pos_stores = sorted(set(datasets["pos_sales"]["store_id"].astype(str)) - valid_store_ids)
    checks.append({
        "check": "pos_sales: store_id references exist in stores",
        "passed": len(invalid_pos_stores) == 0,
        "invalid_count": len(invalid_pos_stores),
        "examples": invalid_pos_stores[:10],
    })

    inv_df = datasets["inventory"]
    store_rows = inv_df[inv_df["location_type"] == "store"]
    invalid_inv_stores = sorted(set(store_rows["location_id"].astype(str)) - valid_store_ids)
    checks.append({
        "check": "inventory: store location_id references exist in stores",
        "passed": len(invalid_inv_stores) == 0,
        "invalid_count": len(invalid_inv_stores),
        "examples": invalid_inv_stores[:10],
    })

    valid_fulfillment = valid_store_ids | valid_warehouse_ids
    invalid_fulfillment = sorted(set(datasets["orders"]["fulfillment_location"].astype(str)) - valid_fulfillment)
    checks.append({
        "check": "orders: fulfillment_location references exist in stores or warehouse",
        "passed": len(invalid_fulfillment) == 0,
        "invalid_count": len(invalid_fulfillment),
        "examples": invalid_fulfillment[:10],
    })

    for name, cols in QUANTITY_COLUMNS.items():
        df = datasets[name]
        for col in cols:
            neg_count = int((df[col] < 0).sum())
            checks.append({
                "check": f"{name}.{col}: no negative values",
                "passed": neg_count == 0,
                "invalid_count": neg_count,
                "examples": [],
            })

    return checks


def _data_freshness(datasets, reference_date=None):
    reference_date = pd.Timestamp.now().normalize() if reference_date is None else reference_date
    freshness = []
    for name, date_column in FRESHNESS_DATE_COLUMNS.items():
        series = pd.to_datetime(datasets[name][date_column], errors="coerce")
        most_recent = series.max()
        if pd.isna(most_recent):
            freshness.append({
                "dataset": name, "date_column": date_column,
                "most_recent_date": None, "days_since_most_recent": None,
            })
        else:
            freshness.append({
                "dataset": name, "date_column": date_column,
                "most_recent_date": str(most_recent.date()),
                "days_since_most_recent": int((reference_date - most_recent.normalize()).days),
            })
    return freshness


def build_quality_report(reference_date=None, service=None):
    """The full structured data quality report. Raises FileNotFoundError/
    ValueError (unchanged from the connectors) if a required dataset file
    or column is missing -- never silently substitutes empty data.

    `service` should be the API's shared, cached RetailDataService
    instance (see api/dependencies.py) so this report reuses already-
    loaded datasets instead of re-reading every CSV file from disk; a new
    instance is constructed only when no service is supplied (e.g. a
    standalone/CLI call)."""
    service = service if service is not None else RetailDataService()
    datasets = _load_all_datasets(service)
    dataset_summaries = _dataset_summaries(datasets)
    validation_checks = _validation_checks(datasets)
    data_freshness = _data_freshness(datasets, reference_date=reference_date)

    overall_passed = (
        all(c["passed"] for c in validation_checks)
        and all(not d["missing_value_counts"] for d in dataset_summaries)
        and all((d["duplicate_record_count"] or 0) == 0 for d in dataset_summaries)
    )

    return {
        "overall_passed": overall_passed,
        "datasets": dataset_summaries,
        "validation_checks": validation_checks,
        "data_freshness": data_freshness,
        "note": (
            "This dataset is a static synthetic CSV snapshot, not a continuously refreshed live feed -- "
            "a nonzero days_since_most_recent value reflects how long ago the snapshot's most recent "
            "record is dated, not a live data-pipeline delay."
        ),
    }
