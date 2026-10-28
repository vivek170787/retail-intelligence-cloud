"use client";

/**
 * Detailed per-SKU replenishment recommendation view. Every figure comes
 * from the existing Inventory Intelligence Agent (GET /inventory/{sku})
 * and, for the forecast-demand cross-check only, the Demand Forecasting
 * Agent (GET /demand/{sku}/forecast, /demand/{sku}/compare-inventory) --
 * no new business logic, no recomputation of the suggested quantity here.
 * The rationale section below only narrates numbers the backend already
 * returned; it never re-derives a figure the engine didn't expose (e.g.
 * the exact velocity used for sizing is only shown when the configured
 * velocity window is 7 or 30 days, since those are the only two windows
 * InventoryRiskEngine actually reports back).
 *
 * Strictly read-only: there is no action anywhere in this component (or
 * this backend) that creates a purchase order, transfers stock, or writes
 * to any operational record.
 */

import { useEffect, useMemo, useRef, useState } from "react";
import { X } from "lucide-react";

import {
  ApiError,
  getCompareForecastWithInventory,
  getDemandForecast,
  getProductInventoryAnalysis,
  getSalesHistory,
} from "@/lib/api";
import type { CompareForecastWithInventory, DemandForecastResult, InventoryRiskItem, SalesTrendResponse } from "@/lib/types";
import { Badge } from "@/components/ui/Badge";
import { DataTable, type DataTableColumn } from "@/components/ui/DataTable";
import { SelectFilter } from "@/components/ui/SelectFilter";
import { DemandTrendChart, type DemandTrendPoint } from "@/components/retail/DemandTrendChart";
import { EmptyState } from "@/components/retail/EmptyState";
import { ErrorState } from "@/components/retail/ErrorState";
import { EvidencePanel } from "@/components/retail/EvidencePanel";
import { LoadingState } from "@/components/retail/LoadingState";
import { SeverityBadge } from "@/components/retail/SeverityBadge";

const HORIZON_OPTIONS = [
  { value: "7", label: "7 days" },
  { value: "14", label: "14 days" },
  { value: "30", label: "30 days" },
];

const BASIS_LABELS: Record<string, string> = {
  target_days_of_coverage: "Based on recent sales velocity (target days of coverage)",
  no_recent_sales_velocity: "Low confidence -- no recent sales velocity data",
};

function buildRationale(analysis: InventoryRiskItem): string[] {
  const { estimated, recommendation, observed, settings_used } = analysis;
  const lines: string[] = [];

  if (recommendation.basis === "no_recent_sales_velocity") {
    lines.push(
      "No recommendation basis: this SKU has zero recent sales velocity, so a target-coverage quantity cannot " +
        "be computed. Suggested quantity is 0."
    );
    return lines;
  }

  const window = estimated.velocity_window_days_used_for_risk;
  const velocity = window === 7 ? estimated.avg_daily_sales_7d : window === 30 ? estimated.avg_daily_sales_30d : null;
  const targetDays = settings_used.replenishment_target_days;

  if (velocity != null) {
    const targetUnits = Math.round(velocity * targetDays * 100) / 100;
    lines.push(
      `Target coverage: ${velocity} unit(s)/day (${window}-day average sales velocity) x ${targetDays} day(s) ` +
        `coverage target = ${targetUnits} unit(s).`
    );
  } else {
    lines.push(
      `Target coverage: recent sales velocity over a ${window}-day window x ${targetDays} day(s) coverage ` +
        "target (exact per-day figure not separately reported for this window length -- see Avg Daily Sales above)."
    );
  }
  lines.push(
    `Minus current available inventory (${observed.store_available_inventory} unit(s), all stores combined) ` +
      "= raw suggested quantity."
  );

  if (recommendation.capped_by_warehouse_availability) {
    lines.push(
      `Raw suggested quantity exceeded eligible warehouse stock (${observed.warehouse.warehouse_available} ` +
        `unit(s)) -- a supply constraint. Final suggested quantity is capped at that availability: ` +
        `${recommendation.suggested_replenishment_quantity} unit(s).`
    );
  } else {
    lines.push(
      `Final suggested quantity: ${recommendation.suggested_replenishment_quantity} unit(s) -- not capped; ` +
        `eligible warehouse stock (${observed.warehouse.warehouse_available} unit(s)) covers the raw suggestion.`
    );
  }

  return lines;
}

export function ReplenishmentDetailDrawer({ sku, onClose }: { sku: string; onClose: () => void }) {
  const [horizonDays, setHorizonDays] = useState(7);
  const [analysis, setAnalysis] = useState<InventoryRiskItem | null>(null);
  const [salesHistory, setSalesHistory] = useState<SalesTrendResponse | null>(null);
  const [forecast, setForecast] = useState<DemandForecastResult | null>(null);
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
      getProductInventoryAnalysis(sku),
      getSalesHistory(sku),
      getDemandForecast(sku, horizonDays),
      getCompareForecastWithInventory(sku, horizonDays),
    ])
      .then(([a, s, f, c]) => {
        if (cancelled) return;
        setAnalysis(a);
        setSalesHistory(s);
        setForecast(f);
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
  }, [sku, horizonDays]);

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

  const storeColumns: DataTableColumn<{ store_id: string; store_name: string; available_quantity: number }>[] = [
    { key: "store_id", header: "Store", accessor: (r) => `${r.store_name} (${r.store_id})` },
    {
      key: "qty",
      header: "Available Qty",
      align: "right",
      sortable: true,
      accessor: (r) => r.available_quantity,
      render: (r) =>
        r.available_quantity <= 0 ? (
          <Badge label="Out of stock here" tone="danger" />
        ) : (
          r.available_quantity
        ),
    },
  ];

  const warehouseColumns: DataTableColumn<{ warehouse_id: string; available: number; inbound_quantity: number; supplier_lead_time_days: number | null }>[] = [
    { key: "warehouse_id", header: "Warehouse", accessor: (r) => r.warehouse_id },
    { key: "available", header: "Eligible Available", align: "right", accessor: (r) => r.available },
    { key: "inbound", header: "Eligible Inbound", align: "right", accessor: (r) => r.inbound_quantity },
    {
      key: "lead_time",
      header: "Supplier Lead Time (days)",
      align: "right",
      accessor: (r) => r.supplier_lead_time_days,
      render: (r) => r.supplier_lead_time_days ?? "Unknown",
    },
  ];

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-black/30" onClick={onClose} aria-hidden="true" />
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="replenishment-detail-title"
        tabIndex={-1}
        className="relative z-50 flex h-full w-full max-w-2xl flex-col overflow-y-auto bg-[var(--ric-card-bg)] shadow-lg outline-none"
      >
        <div className="flex items-start justify-between gap-3 border-b border-[var(--ric-border)] px-5 py-4">
          <div>
            <h2 id="replenishment-detail-title" className="text-sm font-semibold text-[var(--ric-text-primary)]">
              {sku} {analysis?.product?.product_name ? `-- ${analysis.product.product_name}` : ""}
            </h2>
            <p className="mt-0.5 text-xs text-[var(--ric-text-secondary)]">Replenishment recommendation detail</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            title="Close"
            className="rounded-md p-1.5 text-[var(--ric-text-secondary)] hover:bg-[var(--ric-page-bg)]"
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>

        <div className="flex-1 space-y-6 px-5 py-4">
          {loading && <LoadingState message="Loading replenishment detail..." />}
          {error && <ErrorState message={error} />}

          {analysis && !loading && (
            <>
              <div className="flex flex-wrap items-center gap-2">
                <SeverityBadge value={analysis.estimated.risk_level} />
                {analysis.data_as_of && (
                  <span className="text-xs text-[var(--ric-text-secondary)]">Data as of {analysis.data_as_of}</span>
                )}
              </div>

              {/* ---- Current inventory (stores & products requiring replenishment) ---- */}
              <section>
                <h3 className="mb-2 text-sm font-semibold text-[var(--ric-text-primary)]">Current inventory</h3>
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                  <div className="rounded-md border border-[var(--ric-border)] p-3">
                    <p className="text-xs text-[var(--ric-text-secondary)]">Available (all stores combined)</p>
                    <p className="mt-1 text-lg font-semibold text-[var(--ric-text-primary)]">
                      {analysis.observed.store_available_inventory}
                    </p>
                  </div>
                  <div className="rounded-md border border-[var(--ric-border)] p-3">
                    <p className="text-xs text-[var(--ric-text-secondary)]">Avg daily sales (7d)</p>
                    <p className="mt-1 text-lg font-semibold text-[var(--ric-text-primary)]">
                      {analysis.estimated.avg_daily_sales_7d}
                    </p>
                  </div>
                  <div className="rounded-md border border-[var(--ric-border)] p-3">
                    <p className="text-xs text-[var(--ric-text-secondary)]">Days of inventory</p>
                    <p className="mt-1 text-lg font-semibold text-[var(--ric-text-primary)]">
                      {analysis.estimated.days_of_inventory ?? "Unavailable"}
                    </p>
                  </div>
                </div>
                <p className="mt-3 mb-1.5 text-xs font-medium text-[var(--ric-text-secondary)]">
                  Stores stocking this SKU (sorted by available quantity)
                </p>
                <DataTable
                  columns={storeColumns}
                  rows={[...analysis.observed.store_breakdown].sort((a, b) => a.available_quantity - b.available_quantity)}
                  rowKey={(r) => r.store_id}
                  emptyMessage="No store-level inventory for this SKU."
                  defaultSortKey="qty"
                  defaultSortDirection="asc"
                />
              </section>

              {/* ---- Forecast demand ---- */}
              <section>
                <div className="mb-2 flex items-center justify-between">
                  <h3 className="text-sm font-semibold text-[var(--ric-text-primary)]">
                    Forecast demand (estimate)
                  </h3>
                  <SelectFilter
                    label="Horizon"
                    value={String(horizonDays)}
                    options={HORIZON_OPTIONS}
                    onChange={(v) => setHorizonDays(Number(v))}
                  />
                </div>
                {salesHistory?.error && <ErrorState message={salesHistory.error} />}
                {trendPoints.length > 0 && <DemandTrendChart points={trendPoints} />}
                {forecast && forecast.sufficient_data ? (
                  <p className="mt-2 text-sm text-[var(--ric-text-primary)]">
                    Total forecast demand, next {forecast.horizon_days} day(s) (<strong>estimate</strong>):{" "}
                    <strong>{forecast.total_forecast_demand}</strong> (method: {forecast.forecast_method})
                  </p>
                ) : forecast ? (
                  <EmptyState message={`Forecast unavailable: ${forecast.reason ?? "insufficient history"}.`} />
                ) : null}
                {compare && compare.forecast_total_demand !== null && (
                  <div className="mt-3 rounded-md border border-[var(--ric-border)] p-3 text-sm">
                    <p className="text-[var(--ric-text-primary)]">
                      Forecast vs. available inventory gap (estimate):{" "}
                      <strong>{compare.estimated_demand_gap_vs_store_available}</strong> (vs. available + inbound:{" "}
                      {compare.estimated_demand_gap_vs_available_plus_inbound})
                    </p>
                    <p className="mt-1 text-xs text-[var(--ric-text-secondary)]">
                      Shown for comparison only -- the suggested quantity below is computed from recent sales
                      velocity, not from this forecast. {compare.disclaimer}
                    </p>
                  </div>
                )}
              </section>

              {/* ---- Safety stock assumptions ---- */}
              <section>
                <h3 className="mb-2 text-sm font-semibold text-[var(--ric-text-primary)]">
                  Safety stock assumptions
                </h3>
                <div className="rounded-md border border-[var(--ric-border)] p-3 text-sm">
                  <p className="text-[var(--ric-text-primary)]">
                    Not separately configured. This agent does not model a distinct safety-stock quantity --
                    instead, the suggested quantity targets a flat{" "}
                    <strong>{analysis.settings_used.replenishment_target_days} day(s)</strong> of sales coverage
                    (<code className="text-xs">replenishment_target_days</code>), which functions as the buffer.
                  </p>
                </div>
              </section>

              {/* ---- Eligible warehouse stock & inbound inventory ---- */}
              <section>
                <h3 className="mb-2 text-sm font-semibold text-[var(--ric-text-primary)]">
                  Eligible warehouse stock &amp; inbound inventory
                </h3>
                <p className="mb-1.5 text-xs text-[var(--ric-text-secondary)]">
                  Total eligible available: {analysis.observed.warehouse.warehouse_available} -- total eligible
                  inbound: {analysis.observed.warehouse.warehouse_inbound}
                </p>
                <DataTable
                  columns={warehouseColumns}
                  rows={analysis.observed.warehouse.by_warehouse}
                  rowKey={(r) => r.warehouse_id}
                  emptyMessage="No warehouse stock recorded for this SKU."
                />
              </section>

              {/* ---- Supply constraints ---- */}
              <section>
                <h3 className="mb-2 text-sm font-semibold text-[var(--ric-text-primary)]">Supply constraints</h3>
                <ul className="list-disc space-y-1 pl-5 text-sm text-[var(--ric-text-primary)]">
                  {analysis.recommendation.capped_by_warehouse_availability && (
                    <li>
                      The suggested quantity is capped by available warehouse stock -- demand at target coverage
                      exceeds what is currently eligible to ship.
                    </li>
                  )}
                  {analysis.observed.warehouse.by_warehouse
                    .filter((w) => w.supplier_lead_time_days != null)
                    .map((w) => (
                      <li key={w.warehouse_id}>
                        {w.warehouse_id}: supplier lead time {w.supplier_lead_time_days} day(s) -- factor this in
                        before committing to a delivery date.
                      </li>
                    ))}
                  {!analysis.recommendation.capped_by_warehouse_availability &&
                    analysis.observed.warehouse.by_warehouse.every((w) => w.supplier_lead_time_days == null) && (
                      <li>No supply constraints recorded for this SKU.</li>
                    )}
                </ul>
              </section>

              {/* ---- Suggested replenishment quantity ---- */}
              <section>
                <h3 className="mb-2 text-sm font-semibold text-[var(--ric-text-primary)]">
                  Suggested replenishment quantity
                </h3>
                <div className="rounded-md border border-[var(--ric-border)] p-3 text-sm">
                  <p className="text-[var(--ric-text-primary)]">
                    Suggested quantity:{" "}
                    <strong>{analysis.recommendation.suggested_replenishment_quantity}</strong> unit(s)
                  </p>
                  <p className="mt-1 text-xs text-[var(--ric-text-secondary)]">
                    {BASIS_LABELS[analysis.recommendation.basis] ?? analysis.recommendation.basis}
                  </p>
                  {analysis.recommendation.capped_by_warehouse_availability && (
                    <Badge label="Capped by warehouse availability" tone="warning" dot />
                  )}
                </div>
              </section>

              {/* ---- Recommendation rationale ---- */}
              <section>
                <h3 className="mb-2 text-sm font-semibold text-[var(--ric-text-primary)]">
                  Recommendation rationale
                </h3>
                <ul className="list-disc space-y-1 pl-5 text-sm text-[var(--ric-text-primary)]">
                  {buildRationale(analysis).map((line, i) => (
                    <li key={i}>{line}</li>
                  ))}
                </ul>
              </section>

              <div className="rounded-md bg-[var(--ric-page-bg)] px-3 py-2.5 text-xs text-[var(--ric-text-secondary)]">
                This is a read-only recommendation for human review. No purchase order, stock transfer, or
                inventory record is created or changed automatically.
              </div>

              <EvidencePanel evidence={{ inventory: analysis, forecast, compare }} />
            </>
          )}
        </div>
      </div>
    </div>
  );
}
