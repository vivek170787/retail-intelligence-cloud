"use client";

/**
 * Per-SKU demand forecast detail drawer. Everything shown here comes from
 * the Demand Forecasting Agent (GET /demand/{sku}/forecast,
 * /demand/{sku}/sales-history, /demand/{sku}/compare-inventory) -- no new
 * business logic, same pattern as InventoryDetailDrawer. The store
 * selector re-fetches a store-level forecast (forecast_demand supports
 * store_id); sales history and the inventory-gap comparison stay
 * catalog-wide (combined across all stores) because the underlying engine
 * methods backing those two endpoints don't accept a store_id -- labeled
 * as such rather than implying a store-level number that doesn't exist.
 */

import { useEffect, useMemo, useRef, useState } from "react";
import { X } from "lucide-react";

import {
  ApiError,
  getCompareForecastWithInventory,
  getDemandForecast,
  getSalesHistory,
} from "@/lib/api";
import type { CompareForecastWithInventory, DemandForecastResult, SalesTrendResponse } from "@/lib/types";
import { SelectFilter, type SelectFilterOption } from "@/components/ui/SelectFilter";
import { Badge } from "@/components/ui/Badge";
import { DemandTrendChart, type DemandTrendPoint } from "@/components/retail/DemandTrendChart";
import { DataGapsPanel } from "@/components/retail/DataGapsPanel";
import { EmptyState } from "@/components/retail/EmptyState";
import { ErrorState } from "@/components/retail/ErrorState";
import { EvidencePanel } from "@/components/retail/EvidencePanel";
import { ForecastErrorMetrics } from "@/components/retail/ForecastErrorMetrics";
import { LoadingState } from "@/components/retail/LoadingState";

const ALL_STORES = "__all__";

const HORIZON_OPTIONS: SelectFilterOption[] = [
  { value: "7", label: "7 days" },
  { value: "14", label: "14 days" },
  { value: "30", label: "30 days" },
];

export function DemandDetailDrawer({
  sku,
  initialHorizonDays = 7,
  storeOptions,
  onClose,
}: {
  sku: string;
  initialHorizonDays?: number;
  storeOptions: SelectFilterOption[];
  onClose: () => void;
}) {
  const [horizonDays, setHorizonDays] = useState(initialHorizonDays);
  const [storeId, setStoreId] = useState(ALL_STORES);
  const [forecast, setForecast] = useState<DemandForecastResult | null>(null);
  const [salesHistory, setSalesHistory] = useState<SalesTrendResponse | null>(null);
  const [compare, setCompare] = useState<CompareForecastWithInventory | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;

    Promise.resolve().then(() => {
      if (cancelled) return;
      setLoading(true);
      setError(null);
    });

    Promise.all([
      getDemandForecast(sku, horizonDays, storeId === ALL_STORES ? undefined : storeId),
      getSalesHistory(sku),
      getCompareForecastWithInventory(sku, horizonDays),
    ])
      .then(([f, s, c]) => {
        if (cancelled) return;
        setForecast(f);
        setSalesHistory(s);
        setCompare(c);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setError(err instanceof ApiError ? err.message : "An unexpected error occurred.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [sku, horizonDays, storeId]);

  useEffect(() => {
    panelRef.current?.focus();
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  const trendPoints: DemandTrendPoint[] = useMemo(() => {
    const byDate = new Map<string, DemandTrendPoint>();
    for (const [i, date] of (salesHistory?.dates ?? []).entries()) {
      byDate.set(date, { date, historical: salesHistory!.values[i] });
    }
    if (forecast?.sufficient_data && forecast.forecast_daily && forecast.forecast_start_date) {
      const start = new Date(forecast.forecast_start_date);
      forecast.forecast_daily.forEach((value, i) => {
        const d = new Date(start);
        d.setDate(d.getDate() + i);
        const key = d.toISOString().slice(0, 10);
        const existing = byDate.get(key) ?? { date: key };
        byDate.set(key, { ...existing, forecast: value });
      });
    }
    return [...byDate.values()].sort((a, b) => a.date.localeCompare(b.date));
  }, [salesHistory, forecast]);

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-black/30" onClick={onClose} aria-hidden="true" />
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="demand-detail-title"
        tabIndex={-1}
        className="relative z-50 flex h-full w-full max-w-2xl flex-col overflow-y-auto bg-[var(--ric-card-bg)] shadow-lg outline-none"
      >
        <div className="flex items-start justify-between gap-3 border-b border-[var(--ric-border)] px-5 py-4">
          <div>
            <h2 id="demand-detail-title" className="text-sm font-semibold text-[var(--ric-text-primary)]">
              {sku} {forecast?.product_name ? `-- ${forecast.product_name}` : ""}
            </h2>
            <p className="mt-0.5 text-xs text-[var(--ric-text-secondary)]">Demand forecast detail (estimate)</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            title="Close"
            className="rounded-lg p-1.5 text-[var(--ric-text-secondary)] hover:bg-[var(--ric-page-bg)]"
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>

        <div className="flex-1 space-y-6 px-5 py-4">
          {loading && <LoadingState message="Loading demand forecast..." />}
          {error && <ErrorState message={error} />}

          {forecast && !loading && (
            <>
              <div className="flex flex-wrap items-end gap-3">
                <SelectFilter
                  label="Horizon"
                  value={String(horizonDays)}
                  options={HORIZON_OPTIONS}
                  onChange={(v) => setHorizonDays(Number(v))}
                />
                <SelectFilter
                  label="Store (forecast only)"
                  value={storeId}
                  options={[{ value: ALL_STORES, label: "All stores (combined)" }, ...storeOptions]}
                  onChange={setStoreId}
                />
              </div>
              <p className="text-xs text-[var(--ric-text-secondary)]">
                Historical sales, the inventory-gap comparison below, and the backtest always combine all stores --
                only the forecast total reflects the selected store.
              </p>

              {!forecast.sufficient_data && (
                <EmptyState
                  message={`Forecast unavailable for this SKU${forecast.store_name ? ` at ${forecast.store_name}` : ""}: ${
                    forecast.reason ?? "insufficient history"
                  }.`}
                />
              )}

              {/* ---- Historical sales vs. forecast (estimate) ---- */}
              <section>
                <h3 className="mb-2 text-sm font-semibold text-[var(--ric-text-primary)]">
                  Historical sales vs. forecast (estimate)
                </h3>
                {salesHistory?.error && <ErrorState message={salesHistory.error} />}
                {salesHistory && !salesHistory.error && trendPoints.length === 0 && (
                  <EmptyState message="No confirmed sales history for this SKU." />
                )}
                {trendPoints.length > 0 && <DemandTrendChart points={trendPoints} />}

                {forecast.sufficient_data && (
                  <div className="mt-2 rounded-lg border border-[var(--ric-border)] p-3 text-sm">
                    <p className="text-[var(--ric-text-primary)]">
                      Forecast total, next {forecast.horizon_days} day(s) (<strong>estimate</strong>):{" "}
                      <strong>{forecast.total_forecast_demand}</strong>
                      {forecast.store_name ? ` at ${forecast.store_name}` : " (all stores combined)"}
                    </p>
                    <p className="mt-1 text-xs text-[var(--ric-text-secondary)]">
                      Method: {forecast.forecast_method} -- historical average daily sales:{" "}
                      {forecast.historical_avg_daily_sales} over {forecast.historical_period.days_covered}{" "}
                      confirmed day(s) ({forecast.historical_period.start} to {forecast.historical_period.end}).
                    </p>
                    {forecast.seasonal_naive_comparison.total != null ? (
                      <p className="mt-1 text-xs text-[var(--ric-text-secondary)]">
                        Day-of-week seasonal-naive comparison (reference only, not the primary forecast --
                        estimate): {forecast.seasonal_naive_comparison.total}
                      </p>
                    ) : (
                      <p className="mt-1 text-xs text-[var(--ric-text-secondary)]">
                        Seasonal-naive comparison unavailable:{" "}
                        {forecast.seasonal_naive_comparison.unavailable_reason}
                      </p>
                    )}
                  </div>
                )}

                <DataGapsPanel gaps={forecast.data_quality_warnings} />
              </section>

              {/* ---- Forecast error metrics (backtest) ---- */}
              <section>
                <h3 className="mb-2 text-sm font-semibold text-[var(--ric-text-primary)]">
                  Forecast error metrics (backtest)
                </h3>
                <ForecastErrorMetrics backtest={forecast.backtest} />
              </section>

              {/* ---- Forecast vs. inventory (estimate) ---- */}
              {compare && (
                <section>
                  <h3 className="mb-2 text-sm font-semibold text-[var(--ric-text-primary)]">
                    Forecast vs. current inventory
                  </h3>
                  {compare.forecast_total_demand !== null ? (
                    <div className="rounded-lg border border-[var(--ric-border)] p-3 text-sm">
                      <p className="text-[var(--ric-text-primary)]">
                        Estimated demand gap vs. available inventory (all stores combined):{" "}
                        <strong>{compare.estimated_demand_gap_vs_store_available}</strong> (vs. available + inbound:{" "}
                        {compare.estimated_demand_gap_vs_available_plus_inbound})
                      </p>
                      {compare.recommend_investigating_replenishment && (
                        <Badge label="Investigate replenishment" tone="warning" dot />
                      )}
                      <p className="mt-1 text-xs text-[var(--ric-text-secondary)]">{compare.disclaimer}</p>
                    </div>
                  ) : (
                    <EmptyState message="Forecast vs. inventory comparison unavailable (insufficient history)." />
                  )}
                </section>
              )}

              <EvidencePanel evidence={{ forecast, compare, sales_history: salesHistory }} />
            </>
          )}
        </div>
      </div>
    </div>
  );
}
