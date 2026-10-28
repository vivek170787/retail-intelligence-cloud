"""
Deterministic demand forecasting for the Demand Forecasting Agent.

Pure, side-effect-free functions (no I/O) implement the statistical
baseline, backtesting, and change-detection math, kept separate from
DemandForecastEngine's data-orchestration methods so the forecasting logic
is unit-testable with constructed inputs, independent of the data layer.

Forecasting method -- deliberately simple and transparent:
  Primary: a weighted moving average (WMA) over the most recent
  `moving_average_window_days` of confirmed daily sales, with more recent
  days weighted more heavily. Every day in the forecast horizon gets the
  same flat daily rate. This does not capture day-of-week seasonality,
  trend, or promotions -- it is a baseline, not a predictive model.

  Secondary (comparison only, not used to override the primary): a
  day-of-week seasonal-naive forecast, offered only when there is enough
  history (>= `min_weeks_for_seasonal_naive` occurrences of every weekday)
  to make it meaningful.

Missing dates are NOT blindly treated as zero. A date counts as a
confirmed zero-sales day for a given SKU only if the overall sales dataset
(or, for store-level forecasts, that store's own sales) recorded at least
one transaction somewhere on that date -- i.e. the system is confirmed to
have been operating. Calendar days with no transactions anywhere are
excluded from the series as unknown coverage, not fabricated as zero, and
surfaced as a data-quality warning.
"""

import pandas as pd

from services.retail_data_service import RetailDataService
from demand_forecasting_agent.config import DemandForecastSettings


# --------------------------------------------------------------------- #
# Pure data-cleaning and statistical functions -- no I/O
# --------------------------------------------------------------------- #
def dedupe_transactions(sales_df):
    """Drop duplicate transaction rows (by transaction_id when present)."""
    if sales_df is None or len(sales_df) == 0:
        return sales_df
    if "transaction_id" in sales_df.columns:
        return sales_df.drop_duplicates(subset=["transaction_id"])
    return sales_df.drop_duplicates()


def clean_quantities(sales_df):
    """Drop rows with negative/non-numeric quantity_sold rather than
    silently coercing them. Returns (clean_df, invalid_row_count)."""
    if sales_df is None or len(sales_df) == 0:
        return sales_df, 0
    df = sales_df.copy()
    qty = pd.to_numeric(df["quantity_sold"], errors="coerce")
    valid_mask = qty.notna() & (qty >= 0)
    invalid_count = int((~valid_mask).sum())
    df = df.loc[valid_mask].copy()
    df["quantity_sold"] = qty.loc[valid_mask]
    return df, invalid_count


def global_confirmed_dates(scope_sales_df):
    """Calendar dates (as pandas Timestamps, normalized) where the given
    sales scope (all sales, or one store's sales) recorded at least one
    transaction -- i.e. the system is confirmed to have been operating.
    Used to justify zero-filling a specific SKU's missing dates: a missing
    row for THIS sku on a confirmed-operating day means zero sales, not
    unknown data. Days with no transactions anywhere in scope are NOT
    assumed to be zero."""
    if scope_sales_df is None or len(scope_sales_df) == 0:
        return set()
    dates = pd.to_datetime(scope_sales_df["transaction_date"], errors="coerce").dt.normalize()
    return set(dates.dropna())


def build_daily_series(sku_sales_df, confirmed_dates):
    """Build a confirmed daily quantity series for one SKU (optionally
    already filtered to one store), spanning confirmed_dates' min..max.
    Zero-fills only dates present in confirmed_dates; days outside it are
    excluded rather than fabricated. Returns (series, unknown_coverage_days)."""
    if not confirmed_dates:
        return pd.Series(dtype=float), 0

    full_index = pd.DatetimeIndex(sorted(confirmed_dates))

    if sku_sales_df is not None and len(sku_sales_df) > 0:
        dates = pd.to_datetime(sku_sales_df["transaction_date"], errors="coerce").dt.normalize()
        qty = pd.to_numeric(sku_sales_df["quantity_sold"], errors="coerce").fillna(0.0).clip(lower=0)
        daily = pd.Series(qty.values, index=dates).groupby(level=0).sum()
    else:
        daily = pd.Series(dtype=float)

    series = daily.reindex(full_index, fill_value=0.0)

    full_calendar_range = pd.date_range(full_index.min(), full_index.max(), freq="D")
    unknown_coverage_days = len(full_calendar_range) - len(full_index)

    return series, int(unknown_coverage_days)


def weighted_moving_average(series, window_days):
    """Average of the last `window_days` confirmed values, linearly
    weighted so more recent days count more. Returns (value, points_used)."""
    if series is None or len(series) == 0:
        return 0.0, 0
    tail = series.iloc[-window_days:] if len(series) > window_days else series
    n = len(tail)
    if n == 0:
        return 0.0, 0
    weights = pd.Series(range(1, n + 1), index=tail.index)
    weighted_avg = float((tail * weights).sum() / weights.sum())
    return weighted_avg, n


def seasonal_naive_forecast(series, horizon_days, forecast_start_date, min_weeks):
    """Forecast each future day using the historical average for that same
    day-of-week. Returns (list_of_daily_values, None) on success, or
    (None, reason) if there isn't enough history for every weekday."""
    if series is None or len(series) == 0 or forecast_start_date is None:
        return None, "no_history"
    weekday_groups = series.groupby(series.index.day_of_week)
    counts = weekday_groups.count()
    if len(counts) < 7 or counts.min() < min_weeks:
        return None, "insufficient_weeks_per_weekday"
    weekday_avg = weekday_groups.mean()
    future_dates = pd.date_range(forecast_start_date, periods=horizon_days, freq="D")
    daily_values = [float(weekday_avg.loc[d.day_of_week]) for d in future_dates]
    return daily_values, None


def forecast_core(series, unknown_coverage_days, horizon_days, settings, forecast_start_date):
    """Compute the primary (WMA) forecast plus the optional seasonal-naive
    comparison for an already-built daily series. Pure function -- no I/O."""
    history_days_available = len(series)
    result = {
        "history_days_available": history_days_available,
        "historical_avg_daily_sales": None,
        "primary_method": None,
        "primary_method_window_days_used": 0,
        "forecast_daily": None,
        "forecast_total": None,
        "seasonal_naive_daily": None,
        "seasonal_naive_total": None,
        "seasonal_naive_unavailable_reason": None,
        "warnings": [],
        "reason": None,
    }

    if history_days_available < settings.min_history_days_for_forecast:
        result.update({
            "sufficient_data": False,
            "reason": "insufficient_history",
            "seasonal_naive_unavailable_reason": "insufficient_history",
        })
        return result

    warnings = []
    if unknown_coverage_days > 0:
        warnings.append(
            f"{unknown_coverage_days} day(s) in the overall date range had no "
            f"confirmed sales activity anywhere in the data and were excluded "
            f"rather than assumed to be zero."
        )

    wma_value, points_used = weighted_moving_average(series, settings.moving_average_window_days)
    primary_daily = [round(wma_value, 2)] * horizon_days

    seasonal_daily, seasonal_reason = seasonal_naive_forecast(
        series, horizon_days, forecast_start_date, settings.min_weeks_for_seasonal_naive
    )

    result.update({
        "sufficient_data": True,
        "historical_avg_daily_sales": round(float(series.mean()), 2),
        "primary_method": "weighted_moving_average",
        "primary_method_window_days_used": points_used,
        "forecast_daily": primary_daily,
        "forecast_total": round(sum(primary_daily), 2),
        "seasonal_naive_daily": [round(v, 2) for v in seasonal_daily] if seasonal_daily else None,
        "seasonal_naive_total": round(sum(seasonal_daily), 2) if seasonal_daily else None,
        "seasonal_naive_unavailable_reason": seasonal_reason,
        "warnings": warnings,
    })
    return result


def backtest(series, settings):
    """Time-based backtest: train on everything before the last
    `backtest_holdout_days`, predict that holdout with both the WMA method
    and a plain (unweighted) historical-average baseline, and score both
    against the actual holdout values. Never shuffles -- strictly
    chronological train/holdout split, so there is no future-data leakage."""
    holdout_days = settings.backtest_holdout_days
    min_train = settings.min_train_days_for_backtest
    history_days_available = 0 if series is None else len(series)

    if series is None or history_days_available < (min_train + holdout_days):
        return {
            "evaluated": False,
            "reason": "insufficient_history_for_backtest",
            "history_days_available": history_days_available,
            "min_days_required": min_train + holdout_days,
        }

    train = series.iloc[:-holdout_days]
    holdout = series.iloc[-holdout_days:]

    wma_value, _ = weighted_moving_average(train, settings.moving_average_window_days)
    simple_avg = float(train.mean())

    def _metrics(flat_prediction_value):
        predictions = pd.Series(flat_prediction_value, index=holdout.index)
        errors = predictions - holdout
        abs_errors = errors.abs()
        total_actual = float(holdout.sum())
        wape = float(abs_errors.sum() / total_actual) if total_actual > 0 else None
        return {
            "mae": round(float(abs_errors.mean()), 3),
            "wape": round(wape, 3) if wape is not None else None,
            "bias": round(float(errors.mean()), 3),
        }

    return {
        "evaluated": True,
        "train_days": len(train),
        "holdout_days": holdout_days,
        "holdout_period": {
            "start": str(holdout.index.min().date()),
            "end": str(holdout.index.max().date()),
        },
        "holdout_total_actual_demand": float(holdout.sum()),
        "zero_actual_demand_in_holdout": float(holdout.sum()) == 0,
        "weighted_moving_average": _metrics(wma_value),
        "simple_average_baseline": _metrics(simple_avg),
    }


def detect_change(series, settings):
    """Compare the most recent `spike_window_days` against the preceding
    `spike_baseline_window_days`. Returns None if there isn't enough history
    for two full, non-overlapping, minimum-sized windows."""
    required = settings.spike_window_days + settings.spike_baseline_window_days
    if series is None or len(series) < required:
        return None

    recent = series.iloc[-settings.spike_window_days:]
    baseline = series.iloc[-required:-settings.spike_window_days]

    if (
        len(recent) < settings.min_data_points_for_change_detection
        or len(baseline) < settings.min_data_points_for_change_detection
    ):
        return None

    recent_avg = float(recent.mean())
    baseline_avg = float(baseline.mean())
    pct_change = None if baseline_avg <= 0 else ((recent_avg - baseline_avg) / baseline_avg) * 100

    return {
        "recent_window_days": len(recent),
        "recent_window_avg": round(recent_avg, 2),
        "baseline_window_days": len(baseline),
        "baseline_window_avg": round(baseline_avg, 2),
        "percent_change": round(pct_change, 1) if pct_change is not None else None,
        "recent_period": (str(recent.index.min().date()), str(recent.index.max().date())),
        "baseline_period": (str(baseline.index.min().date()), str(baseline.index.max().date())),
    }


# --------------------------------------------------------------------- #
# Data-orchestration layer -- wires the pure functions above to
# RetailDataService (and, for inventory comparison, InventoryRiskEngine)
# --------------------------------------------------------------------- #
class DemandForecastEngine:
    def __init__(self, service=None, settings=None, inventory_engine=None):
        self.service = service if service is not None else RetailDataService()
        self.settings = settings if settings is not None else DemandForecastSettings.from_env()
        self._inventory_engine = inventory_engine
        # Per-(sku, horizon_days, store_id) cache for forecast_demand(), the
        # most expensive call here (includes a full backtest). Callers like
        # OrderFulfillmentEngine's per-order demand context call this
        # repeatedly for the same SKU across many orders that share it --
        # a pure function of the already-cached, unchanging underlying
        # data, so memoizing changes no computed value. See
        # InventoryRiskEngine._sku_analysis_cache for the same pattern.
        self._forecast_cache = {}
        # _daily_series_for_sku() is the shared data-assembly step behind
        # forecast_demand(), detect_demand_spikes(), detect_declining_demand(),
        # and get_demand_summary() -- within one get_demand_summary() call it
        # was otherwise rebuilt 3x per SKU (once per caller) for identical
        # input. Cached per (sku, store_id); same reasoning as
        # InventoryRiskEngine._sku_analysis_cache. No downstream code
        # mutates the returned series/bundle in place.
        self._daily_series_cache = {}

    @property
    def inventory_engine(self):
        """Lazily constructed, reusing this engine's own data service so the
        two agents share one cached read of the CSVs rather than loading
        them twice. Not constructed until actually needed."""
        if self._inventory_engine is None:
            from inventory_agent.risk_engine import InventoryRiskEngine
            self._inventory_engine = InventoryRiskEngine(service=self.service)
        return self._inventory_engine

    # ---- shared helpers -------------------------------------------------
    def _validate_store_id(self, store_id):
        if store_id is None:
            return None
        if not isinstance(store_id, str) or not store_id.strip():
            raise ValueError(f"store_id must be a non-empty string, got: {store_id!r}")
        store_id = store_id.strip()
        stores_df = self.service.get_stores()
        if store_id not in set(stores_df["store_id"]):
            raise ValueError(
                f"Unknown store_id: {store_id!r}. Valid store_ids: {sorted(stores_df['store_id'])}"
            )
        return store_id

    def _daily_series_for_sku(self, sku, store_id=None):
        """Core data assembly shared by every public method: validates
        inputs, dedupes/cleans the sales rows, and builds the confirmed
        daily series. Raises ValueError for invalid sku/store_id. Memoized
        per raw (sku, store_id) -- see _daily_series_cache in __init__."""
        cache_key = (sku, store_id)
        if cache_key in self._daily_series_cache:
            return self._daily_series_cache[cache_key]

        sales_df = self.service.get_sales_by_sku(sku)  # validates sku
        store_id = self._validate_store_id(store_id)

        all_sales = self.service.get_sales()
        store_name = None
        if store_id is not None:
            store_row = self.service.get_stores().set_index("store_id").loc[store_id]
            store_name = store_row["store_name"]
            scope_sales = all_sales[all_sales["store_id"] == store_id]
            sales_df = sales_df[sales_df["store_id"] == store_id]
        else:
            scope_sales = all_sales

        sales_df = dedupe_transactions(sales_df)
        sales_df, invalid_qty_count = clean_quantities(sales_df)
        scope_sales = dedupe_transactions(scope_sales)
        scope_sales, _ = clean_quantities(scope_sales)

        confirmed_dates = global_confirmed_dates(scope_sales)
        series, unknown_coverage_days = build_daily_series(sales_df, confirmed_dates)

        products_df = self.service.get_products()
        product_rows = products_df[products_df["sku"] == sku]
        product_found = len(product_rows) > 0
        product = product_rows.iloc[0].to_dict() if product_found else None

        result = {
            "series": series,
            "unknown_coverage_days": unknown_coverage_days,
            "product_found": product_found,
            "product": product,
            "store_id": store_id,
            "store_name": store_name,
            "invalid_qty_count": invalid_qty_count,
        }
        self._daily_series_cache[cache_key] = result
        return result

    def _promotion_overlap(self, sku, period):
        promo_df = self.service.get_promotions(sku)
        if promo_df is None or len(promo_df) == 0:
            return False, []
        period_start, period_end = pd.Timestamp(period[0]), pd.Timestamp(period[1])
        starts = pd.to_datetime(promo_df["start_date"], errors="coerce")
        ends = pd.to_datetime(promo_df["end_date"], errors="coerce")
        overlap_mask = (starts <= period_end) & (ends >= period_start)
        overlapping = promo_df.loc[overlap_mask]
        if len(overlapping) == 0:
            return False, []
        return True, overlapping["promotion_name"].tolist()

    # ---- required public functions --------------------------------------
    def forecast_demand(self, sku, horizon_days=None, store_id=None):
        """Forecast daily demand for one SKU (optionally one store) over
        `horizon_days` (defaults to settings.default_horizon_days)."""
        horizon_days = self.settings.default_horizon_days if horizon_days is None else horizon_days
        if not isinstance(horizon_days, int) or isinstance(horizon_days, bool) or horizon_days <= 0:
            raise ValueError(f"horizon_days must be a positive integer, got: {horizon_days!r}")

        cache_key = (sku, horizon_days, store_id)
        if cache_key in self._forecast_cache:
            return self._forecast_cache[cache_key]

        bundle = self._daily_series_for_sku(sku, store_id=store_id)
        series = bundle["series"]
        forecast_start = (series.index.max() + pd.Timedelta(days=1)) if len(series) else None

        core = forecast_core(series, bundle["unknown_coverage_days"], horizon_days, self.settings, forecast_start)
        backtest_result = (
            backtest(series, self.settings)
            if core["sufficient_data"]
            else {"evaluated": False, "reason": "insufficient_history_for_backtest"}
        )

        warnings = list(core["warnings"])
        if not bundle["product_found"]:
            warnings.append(f"SKU {sku!r} was not found in the product catalog.")
        if bundle["invalid_qty_count"] > 0:
            warnings.append(
                f"{bundle['invalid_qty_count']} sales record(s) had invalid "
                f"(negative/non-numeric) quantity and were excluded."
            )

        result = {
            "sku": sku,
            "product_found": bundle["product_found"],
            "product_name": bundle["product"]["product_name"] if bundle["product"] else None,
            "store_id": bundle["store_id"],
            "store_name": bundle["store_name"],
            "horizon_days": horizon_days,
            "historical_period": {
                "start": str(series.index.min().date()) if len(series) else None,
                "end": str(series.index.max().date()) if len(series) else None,
                "days_covered": core["history_days_available"],
            },
            "sufficient_data": core["sufficient_data"],
            "reason": core["reason"],
            "historical_avg_daily_sales": core["historical_avg_daily_sales"],
            "forecast_method": core["primary_method"],
            "forecast_daily": core["forecast_daily"],
            "forecast_start_date": str(forecast_start.date()) if forecast_start is not None else None,
            "total_forecast_demand": core["forecast_total"],
            "seasonal_naive_comparison": {
                "daily": core["seasonal_naive_daily"],
                "total": core["seasonal_naive_total"],
                "unavailable_reason": core["seasonal_naive_unavailable_reason"],
            },
            "backtest": backtest_result,
            "data_quality_warnings": warnings,
            "settings_used": self.settings.as_dict(),
        }
        self._forecast_cache[cache_key] = result
        return result

    def get_top_forecasted_products(self, horizon_days=None, limit=10):
        if not isinstance(limit, int) or isinstance(limit, bool) or limit <= 0:
            raise ValueError(f"limit must be a positive integer, got: {limit!r}")
        products_df = self.service.get_products()
        results = [self.forecast_demand(sku, horizon_days=horizon_days) for sku in products_df["sku"]]
        results = [r for r in results if r["sufficient_data"]]
        results.sort(key=lambda r: r["total_forecast_demand"], reverse=True)
        return results[:limit]

    def _detect_changes(self, direction):
        products_df = self.service.get_products()
        product_name_map = dict(zip(products_df["sku"], products_df["product_name"]))
        results = []

        for sku in products_df["sku"]:
            bundle = self._daily_series_for_sku(sku)
            change = detect_change(bundle["series"], self.settings)
            if change is None or change["percent_change"] is None:
                continue

            pct = change["percent_change"]
            if direction == "spike" and pct < self.settings.spike_threshold_pct:
                continue
            if direction == "decline" and pct > -self.settings.decline_threshold_pct:
                continue

            promo_overlap, promo_names = self._promotion_overlap(sku, change["recent_period"])

            results.append({
                "sku": sku,
                "product_name": product_name_map.get(sku, "Unknown product"),
                **change,
                "data_quality_caveat": bundle["unknown_coverage_days"] > 0,
                "promotion_overlap": promo_overlap,
                "promotion_names": promo_names,
                "note": (
                    "A promotion overlaps the recent period; this may or may not explain the change."
                    if promo_overlap else None
                ),
            })

        results.sort(key=lambda r: abs(r["percent_change"]), reverse=True)
        return results

    def detect_demand_spikes(self):
        return self._detect_changes("spike")

    def detect_declining_demand(self):
        return self._detect_changes("decline")

    def get_demand_summary(self, sku=None):
        if sku is not None:
            forecast = self.forecast_demand(sku)
            bundle = self._daily_series_for_sku(sku)
            change = detect_change(bundle["series"], self.settings)
            return {
                "sku": sku,
                "product_found": forecast["product_found"],
                "product_name": forecast["product_name"],
                "historical_period": forecast["historical_period"],
                "historical_avg_daily_sales": forecast["historical_avg_daily_sales"],
                "total_forecast_demand_next_horizon": forecast["total_forecast_demand"],
                "forecast_method": forecast["forecast_method"],
                "recent_vs_baseline_change": change,
                "data_quality_warnings": forecast["data_quality_warnings"],
            }

        products_df = self.service.get_products()
        forecasts = [self.forecast_demand(s) for s in products_df["sku"]]
        sufficient = [f for f in forecasts if f["sufficient_data"]]
        spikes = self.detect_demand_spikes()
        declines = self.detect_declining_demand()

        return {
            "total_products": len(forecasts),
            "products_with_sufficient_history": len(sufficient),
            "products_with_insufficient_history": len(forecasts) - len(sufficient),
            "total_forecast_demand_next_horizon": (
                round(sum(f["total_forecast_demand"] for f in sufficient), 2) if sufficient else 0.0
            ),
            "products_with_demand_spike": len(spikes),
            "products_with_declining_demand": len(declines),
            "settings_used": self.settings.as_dict(),
        }

    def compare_forecast_with_inventory(self, sku, horizon_days=None):
        """Compare forecast demand against current inventory via the
        existing Inventory Intelligence Agent's public interface (no
        duplicate inventory data access). This is an estimate for
        investigation only -- never a final replenishment quantity, and
        no inventory/order/transfer action is taken automatically."""
        forecast = self.forecast_demand(sku, horizon_days=horizon_days)
        inventory_analysis = self.inventory_engine.get_product_inventory_analysis(sku)

        available = inventory_analysis["observed"]["store_available_inventory"]
        warehouse = inventory_analysis["observed"]["warehouse"]
        inbound = warehouse["warehouse_inbound"]
        warehouse_available = warehouse["warehouse_available"]
        total_forecast = forecast["total_forecast_demand"]

        limitations = list(forecast["data_quality_warnings"])
        gap_vs_available = None
        gap_vs_available_plus_inbound = None
        recommend_investigating = False

        if forecast["sufficient_data"] and total_forecast is not None:
            gap_vs_available = round(total_forecast - available, 2)
            gap_vs_available_plus_inbound = round(total_forecast - (available + inbound), 2)
            recommend_investigating = gap_vs_available > 0
        else:
            limitations.append(
                "Forecast could not be computed (insufficient history); demand gap is unavailable."
            )

        return {
            "sku": sku,
            "product_name": forecast["product_name"],
            "horizon_days": forecast["horizon_days"],
            "forecast_total_demand": total_forecast,
            "forecast_method": forecast["forecast_method"],
            "current_available_inventory": available,
            "known_inbound_stock": inbound,
            "warehouse_available_stock": warehouse_available,
            "estimated_demand_gap_vs_store_available": gap_vs_available,
            "estimated_demand_gap_vs_available_plus_inbound": gap_vs_available_plus_inbound,
            "inventory_agent_suggested_replenishment_quantity": (
                inventory_analysis["recommendation"]["suggested_replenishment_quantity"]
            ),
            "inventory_agent_risk_level": inventory_analysis["estimated"]["risk_level"],
            "recommend_investigating_replenishment": recommend_investigating,
            "data_limitations": limitations,
            "disclaimer": (
                "This demand gap is an estimate for investigation only -- it is "
                "not a final replenishment quantity, and no inventory, purchase "
                "order, or stock transfer is created automatically."
            ),
        }

    def evaluate_forecast(self, sku, store_id=None):
        """Dedicated backtest entry point (see also forecast_demand()'s
        embedded `backtest` field)."""
        bundle = self._daily_series_for_sku(sku, store_id=store_id)
        return {
            "sku": sku,
            "product_found": bundle["product_found"],
            "store_id": bundle["store_id"],
            "backtest": backtest(bundle["series"], self.settings),
        }


_default_engine = DemandForecastEngine()


def forecast_demand(sku, horizon_days=7, store_id=None):
    return _default_engine.forecast_demand(sku, horizon_days=horizon_days, store_id=store_id)


def get_top_forecasted_products(horizon_days=7, limit=10):
    return _default_engine.get_top_forecasted_products(horizon_days=horizon_days, limit=limit)


def detect_demand_spikes():
    return _default_engine.detect_demand_spikes()


def detect_declining_demand():
    return _default_engine.detect_declining_demand()


def get_demand_summary(sku=None):
    return _default_engine.get_demand_summary(sku=sku)


def compare_forecast_with_inventory(sku, horizon_days=7):
    return _default_engine.compare_forecast_with_inventory(sku, horizon_days=horizon_days)


def evaluate_forecast(sku, store_id=None):
    return _default_engine.evaluate_forecast(sku, store_id=store_id)
