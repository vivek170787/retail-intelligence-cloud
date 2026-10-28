"""
Deterministic inventory business logic for the Inventory Intelligence Agent.

Pure, side-effect-free calculation functions (module-level, no I/O) are
kept separate from InventoryRiskEngine's data-orchestration methods (which
call RetailDataService) so the business rules can be unit tested directly
with constructed inputs, independent of the data layer.

Design notes:
- "Available inventory" (used for stockout risk) is STORE-ONLY, taken from
  inventory.csv rows where location_type == "store". Warehouse capacity is
  tracked separately via warehouse.csv (RetailDataService.get_warehouse_stock),
  since the two datasets were generated independently and are not numerically
  reconciled -- mixing them would double count or misrepresent stock.
- Sales velocity windows are computed relative to the latest transaction_date
  present in the data (not wall-clock time), so metrics stay stable regardless
  of when the agent happens to run relative to the synthetic data's date range.
- Every per-SKU result is split into "observed" (facts straight from the
  data), "estimated" (derived/interpreted numbers: velocity, days of
  inventory, risk level), and "recommendation" (replenishment suggestion) so
  the three are never ambiguous to a caller or an LLM.
"""

import math
from datetime import timedelta

import pandas as pd

from services.retail_data_service import RetailDataService
from inventory_agent.config import (
    InventoryRiskSettings,
    OPEN_ORDER_STATUSES,
    RISK_CRITICAL,
    RISK_HIGH,
    RISK_LOW,
    RISK_MEDIUM,
    RISK_SEVERITY_ORDER,
    RISK_UNKNOWN,
)


# --------------------------------------------------------------------- #
# Pure business-rule functions -- no I/O, fully unit-testable in isolation
# --------------------------------------------------------------------- #
def clip_non_negative_sum(series):
    """Sum a numeric series, treating missing/negative values as zero."""
    if series is None or len(series) == 0:
        return 0.0
    return float(series.fillna(0).clip(lower=0).sum())


def avg_daily_sales(sales_df, reference_date, window_days):
    """Average daily units sold over the last `window_days` calendar days
    ending at `reference_date` (inclusive). Returns 0.0 if there is no
    usable sales data or reference date."""
    if sales_df is None or len(sales_df) == 0 or reference_date is None or window_days <= 0:
        return 0.0
    window_start = reference_date - timedelta(days=window_days)
    mask = sales_df["transaction_date"] > window_start
    total = clip_non_negative_sum(sales_df.loc[mask, "quantity_sold"])
    return total / window_days


def days_of_inventory(available_inventory, sales_velocity):
    """Days of inventory = available inventory / average daily sales.
    Returns None ("unavailable") if average daily sales is zero, instead
    of dividing by zero."""
    if sales_velocity is None or sales_velocity <= 0:
        return None
    return max(0.0, available_inventory) / sales_velocity


def classify_risk(available_inventory, sales_velocity, days_remaining, settings):
    """Classify stockout risk.

    - unknown: no sales velocity to assess risk against (avg daily sales is
      zero), regardless of current stock level.
    - critical: no available inventory at all, with positive recent sales
      (takes priority over the day-based thresholds below).
    - high: fewer than `settings.high_risk_days_threshold` days of inventory.
    - medium: between high and `settings.medium_risk_days_threshold` days.
    - low: `settings.medium_risk_days_threshold` days or more.
    """
    if sales_velocity is None or sales_velocity <= 0:
        return RISK_UNKNOWN
    if available_inventory is None or available_inventory <= 0:
        return RISK_CRITICAL
    if days_remaining is None:
        return RISK_UNKNOWN
    if days_remaining < settings.high_risk_days_threshold:
        return RISK_HIGH
    if days_remaining < settings.medium_risk_days_threshold:
        return RISK_MEDIUM
    return RISK_LOW


def is_excess_inventory(available_inventory, sales_velocity, days_remaining, settings):
    """Flag excess stock: either comfortably more days of coverage than
    needed, or a meaningful stockpile sitting against zero recent demand."""
    if sales_velocity and sales_velocity > 0 and days_remaining is not None:
        return days_remaining > settings.excess_days_threshold
    return (available_inventory or 0.0) > settings.excess_no_sales_min_units


def suggested_replenishment(available_inventory, sales_velocity, warehouse_available, settings):
    """Suggested replenishment quantity, targeting `replenishment_target_days`
    of coverage, never exceeding eligible warehouse stock. Returns
    (quantity: int, basis: str, was_capped_by_warehouse: bool)."""
    warehouse_available = max(0.0, warehouse_available or 0.0)
    if sales_velocity is None or sales_velocity <= 0:
        return 0, "no_recent_sales_velocity", False

    target_units = sales_velocity * settings.replenishment_target_days
    raw_suggested = max(0.0, target_units - max(0.0, available_inventory or 0.0))
    capped_value = min(raw_suggested, warehouse_available)
    final_qty = int(math.floor(capped_value))
    was_capped = raw_suggested > warehouse_available
    return final_qty, "target_days_of_coverage", was_capped


# --------------------------------------------------------------------- #
# Data-orchestration layer -- wires the pure rules above to RetailDataService
# --------------------------------------------------------------------- #
class InventoryRiskEngine:
    def __init__(self, service=None, settings=None):
        self.service = service if service is not None else RetailDataService()
        self.settings = settings if settings is not None else InventoryRiskSettings.from_env()

    # ---- shared helpers ------------------------------------------------
    def _reference_date(self):
        sales_df = self.service.get_sales()
        if sales_df is None or len(sales_df) == 0:
            return None
        parsed = pd.to_datetime(sales_df["transaction_date"], errors="coerce")
        if parsed.isna().all():
            return None
        return parsed.max()

    def _warehouse_metrics(self, sku):
        df = self.service.get_warehouse_stock(sku)
        if df is None or len(df) == 0:
            return {"warehouse_available": 0.0, "warehouse_inbound": 0.0, "by_warehouse": []}

        safe = df.copy()
        on_hand = safe["on_hand_quantity"].fillna(0).clip(lower=0)
        reserved = safe["reserved_quantity"].fillna(0).clip(lower=0)
        inbound = safe["inbound_quantity"].fillna(0).clip(lower=0)
        available = (on_hand - reserved).clip(lower=0)

        by_warehouse = []
        for idx in safe.index:
            lead_time = safe.loc[idx, "supplier_lead_time_days"]
            by_warehouse.append({
                "warehouse_id": safe.loc[idx, "warehouse_id"],
                "available": float(available.loc[idx]),
                "inbound_quantity": float(inbound.loc[idx]),
                "supplier_lead_time_days": None if pd.isna(lead_time) else float(lead_time),
            })

        return {
            "warehouse_available": float(available.sum()),
            "warehouse_inbound": float(inbound.sum()),
            "by_warehouse": by_warehouse,
        }

    def _analyze_sku(self, sku, reference_date=None):
        """Full observed/estimated/recommendation analysis for one SKU.
        Raises ValueError for invalid (empty/None) sku input, via the
        underlying RetailDataService's own validation."""
        inventory_df = self.service.get_inventory_by_sku(sku)
        sales_df = self.service.get_sales_by_sku(sku)
        orders_df = self.service.get_orders_by_sku(sku)
        products_df = self.service.get_products()
        stores_df = self.service.get_stores()

        if reference_date is None:
            reference_date = self._reference_date()

        product_rows = products_df[products_df["sku"] == sku]
        product_found = len(product_rows) > 0
        product = product_rows.iloc[0].to_dict() if product_found else None

        store_rows = inventory_df[inventory_df["location_type"] == "store"] if len(inventory_df) else inventory_df
        store_available = clip_non_negative_sum(store_rows["available_quantity"]) if len(store_rows) else 0.0

        store_name_map = dict(zip(stores_df["store_id"], stores_df["store_name"]))
        store_breakdown = [
            {
                "store_id": row["location_id"],
                "store_name": store_name_map.get(row["location_id"], "Unknown store"),
                "available_quantity": max(0.0, float(row["available_quantity"]) if pd.notna(row["available_quantity"]) else 0.0),
            }
            for _, row in store_rows.iterrows()
        ] if len(store_rows) else []

        open_orders = [
            {
                "order_id": row["order_id"],
                "customer_id": row["customer_id"],
                "order_status": row["order_status"],
                "quantity": row["quantity"],
                "promised_delivery_date": row["promised_delivery_date"],
            }
            for _, row in orders_df[orders_df["order_status"].isin(OPEN_ORDER_STATUSES)].iterrows()
        ] if len(orders_df) else []

        avg_7d = avg_daily_sales(sales_df, reference_date, 7)
        avg_30d = avg_daily_sales(sales_df, reference_date, self.settings.secondary_velocity_window_days)
        avg_primary = avg_daily_sales(sales_df, reference_date, self.settings.velocity_window_days)

        days_remaining = days_of_inventory(store_available, avg_primary)
        risk_level = classify_risk(store_available, avg_primary, days_remaining, self.settings)
        excess = is_excess_inventory(store_available, avg_primary, days_remaining, self.settings)

        warehouse = self._warehouse_metrics(sku)
        qty, basis, capped = suggested_replenishment(
            store_available, avg_primary, warehouse["warehouse_available"], self.settings
        )

        return {
            "sku": sku,
            "product_found": product_found,
            "product": product,
            "data_as_of": reference_date.strftime("%Y-%m-%d") if reference_date is not None else None,
            "observed": {
                "store_available_inventory": round(store_available, 2),
                "store_breakdown": store_breakdown,
                "open_orders": open_orders,
                "warehouse": warehouse,
            },
            "estimated": {
                "avg_daily_sales_7d": round(avg_7d, 2),
                "avg_daily_sales_30d": round(avg_30d, 2),
                "velocity_window_days_used_for_risk": self.settings.velocity_window_days,
                "days_of_inventory": round(days_remaining, 2) if days_remaining is not None else None,
                "days_of_inventory_unavailable_reason": (
                    "zero_average_daily_sales" if avg_primary <= 0 else None
                ),
                "risk_level": risk_level,
                "is_excess_inventory": excess,
                "open_orders_count": len(open_orders),
                "open_orders_at_risk": bool(open_orders) and risk_level in (RISK_CRITICAL, RISK_HIGH),
            },
            "recommendation": {
                "suggested_replenishment_quantity": qty,
                "basis": basis,
                "capped_by_warehouse_availability": capped,
            },
            "settings_used": self.settings.as_dict(),
        }

    # ---- required public functions -------------------------------------
    def get_inventory_risks(self):
        """Per-SKU risk assessment for every product in the catalog."""
        products_df = self.service.get_products()
        reference_date = self._reference_date()
        results = [self._analyze_sku(sku, reference_date) for sku in products_df["sku"]]
        results.sort(key=lambda r: RISK_SEVERITY_ORDER.get(r["estimated"]["risk_level"], 99))
        return results

    def get_store_inventory_risks(self, store_id=None):
        """Store-level shortages (critical/high/medium only) for a given
        store, or all stores if store_id is None."""
        stores_df = self.service.get_stores()
        valid_store_ids = set(stores_df["store_id"])

        if store_id is not None:
            if not isinstance(store_id, str) or not store_id.strip():
                raise ValueError(f"store_id must be a non-empty string, got: {store_id!r}")
            store_id = store_id.strip()
            if store_id not in valid_store_ids:
                raise ValueError(
                    f"Unknown store_id: {store_id!r}. Valid store_ids: {sorted(valid_store_ids)}"
                )

        inventory_df = self.service.get_inventory()
        store_rows = inventory_df[inventory_df["location_type"] == "store"]
        if store_id is not None:
            store_rows = store_rows[store_rows["location_id"] == store_id]

        if len(store_rows) == 0:
            return []

        sales_df = self.service.get_sales()
        reference_date = self._reference_date()
        store_name_map = dict(zip(stores_df["store_id"], stores_df["store_name"]))

        products_df = self.service.get_products()
        product_name_map = dict(zip(products_df["sku"], products_df["product_name"]))

        results = []
        for _, row in store_rows.iterrows():
            row_store_id = row["location_id"]
            sku = row["sku"]
            available = max(0.0, float(row["available_quantity"]) if pd.notna(row["available_quantity"]) else 0.0)

            local_sales = sales_df[(sales_df["sku"] == sku) & (sales_df["store_id"] == row_store_id)]
            avg_7d = avg_daily_sales(local_sales, reference_date, 7)
            avg_30d = avg_daily_sales(local_sales, reference_date, self.settings.secondary_velocity_window_days)
            avg_primary = avg_daily_sales(local_sales, reference_date, self.settings.velocity_window_days)

            days_remaining = days_of_inventory(available, avg_primary)
            risk_level = classify_risk(available, avg_primary, days_remaining, self.settings)

            if risk_level not in (RISK_CRITICAL, RISK_HIGH, RISK_MEDIUM):
                continue

            results.append({
                "store_id": row_store_id,
                "store_name": store_name_map.get(row_store_id, "Unknown store"),
                "sku": sku,
                "product_name": product_name_map.get(sku, "Unknown product"),
                "observed": {"available_quantity": round(available, 2)},
                "estimated": {
                    "avg_daily_sales_7d": round(avg_7d, 2),
                    "avg_daily_sales_30d": round(avg_30d, 2),
                    "days_of_inventory": round(days_remaining, 2) if days_remaining is not None else None,
                    "risk_level": risk_level,
                },
            })

        results.sort(key=lambda r: RISK_SEVERITY_ORDER.get(r["estimated"]["risk_level"], 99))
        return results

    def get_product_inventory_analysis(self, sku):
        """Full observed/estimated/recommendation analysis for a single SKU."""
        return self._analyze_sku(sku)

    def get_warehouse_availability(self, sku):
        """Warehouse-only stock availability for a single SKU (validates
        sku via RetailDataService.get_warehouse_stock)."""
        self.service.get_warehouse_stock(sku)  # raises ValueError on bad input
        warehouse = self._warehouse_metrics(sku)
        return {"sku": sku, **warehouse}

    def get_top_stockout_risks(self, limit=10):
        """The `limit` most severe stockout risks, excluding SKUs with no
        sales velocity to assess (risk_level == unknown)."""
        if not isinstance(limit, int) or limit <= 0:
            raise ValueError(f"limit must be a positive integer, got: {limit!r}")

        risks = [
            r for r in self.get_inventory_risks()
            if r["estimated"]["risk_level"] != RISK_UNKNOWN
        ]
        risks.sort(
            key=lambda r: (
                RISK_SEVERITY_ORDER.get(r["estimated"]["risk_level"], 99),
                r["estimated"]["days_of_inventory"] if r["estimated"]["days_of_inventory"] is not None else float("inf"),
            )
        )
        return risks[:limit]

    def get_replenishment_recommendations(self):
        """Every SKU with a positive suggested replenishment quantity,
        most severe risk first."""
        results = [
            r for r in self.get_inventory_risks()
            if r["recommendation"]["suggested_replenishment_quantity"] > 0
        ]
        results.sort(
            key=lambda r: (
                RISK_SEVERITY_ORDER.get(r["estimated"]["risk_level"], 99),
                -r["recommendation"]["suggested_replenishment_quantity"],
            )
        )
        return results

    def get_inventory_summary(self):
        """Aggregate counts across the full catalog."""
        risks = self.get_inventory_risks()
        reference_date = self._reference_date()

        risk_level_counts = {level: 0 for level in RISK_SEVERITY_ORDER}
        excess_count = 0
        replenishment_count = 0
        open_orders_at_risk_count = 0

        for r in risks:
            risk_level_counts[r["estimated"]["risk_level"]] += 1
            if r["estimated"]["is_excess_inventory"]:
                excess_count += 1
            if r["recommendation"]["suggested_replenishment_quantity"] > 0:
                replenishment_count += 1
            if r["estimated"]["open_orders_at_risk"]:
                open_orders_at_risk_count += r["estimated"]["open_orders_count"]

        return {
            "data_as_of": reference_date.strftime("%Y-%m-%d") if reference_date is not None else None,
            "total_products": len(risks),
            "risk_level_counts": risk_level_counts,
            "products_needing_replenishment": replenishment_count,
            "products_with_excess_inventory": excess_count,
            "open_orders_at_risk_count": open_orders_at_risk_count,
            "settings_used": self.settings.as_dict(),
        }


_default_engine = InventoryRiskEngine()


def get_inventory_risks():
    return _default_engine.get_inventory_risks()


def get_store_inventory_risks(store_id=None):
    return _default_engine.get_store_inventory_risks(store_id=store_id)


def get_product_inventory_analysis(sku):
    return _default_engine.get_product_inventory_analysis(sku)


def get_warehouse_availability(sku):
    return _default_engine.get_warehouse_availability(sku)


def get_top_stockout_risks(limit=10):
    return _default_engine.get_top_stockout_risks(limit=limit)


def get_replenishment_recommendations():
    return _default_engine.get_replenishment_recommendations()


def get_inventory_summary():
    return _default_engine.get_inventory_summary()
