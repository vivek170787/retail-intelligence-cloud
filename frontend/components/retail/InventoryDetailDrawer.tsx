"use client";

/**
 * Per-SKU inventory risk detail drawer. Everything shown here comes from
 * the existing Inventory Intelligence Agent (GET /inventory/{sku}) and
 * Demand Forecasting Agent (GET /demand/{sku}/forecast,
 * /demand/{sku}/sales-history, /demand/{sku}/compare-inventory) -- no new
 * business logic, same pattern as every other page in this app. "Next
 * steps" are deterministic labels derived from these agents' own
 * already-computed structured fields (risk level, excess flag, warehouse
 * cap, demand gap) -- never an invented number or claim.
 */

import { useEffect, useMemo, useRef, useState } from "react";
import { X } from "lucide-react";

import { ApiError, getCompareForecastWithInventory, getDemandForecast, getProductInventoryAnalysis, getSalesHistory } from "@/lib/api";
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

function buildNextSteps(
  analysis: InventoryRiskItem | null,
  compare: CompareForecastWithInventory | null
): string[] {
  if (!analysis) return [];
  const steps: string[] = [];
  const { estimated, recommendation } = analysis;

  if (estimated.risk_level === "critical" || estimated.risk_level === "high") {
    steps.push(`Risk level is ${estimated.risk_level} -- investigate replenishment for this SKU first.`);
  }
  if (recommendation.suggested_replenishment_quantity > 0) {
    steps.push(
      `Suggested replenishment quantity: ${recommendation.suggested_replenishment_quantity} ` +
        `(${BASIS_LABELS[recommendation.basis] ?? recommendation.basis}).`
    );
  }
  if (recommendation.capped_by_warehouse_availability) {
    steps.push(
      "The suggested quantity is capped by available warehouse stock -- confirm supplier lead time before " +
        "committing to a delivery date."
    );
  }
  if (estimated.open_orders_at_risk) {
    steps.push(
      `${estimated.open_orders_count} open order(s) are exposed to this risk level -- cross-check with the ` +
        "Order Fulfillment workspace."
    );
  }
  if (estimated.is_excess_inventory) {
    steps.push(
      "This SKU is flagged as excess inventory -- consider reducing future replenishment or reallocating stock."
    );
  }
  if (compare && compare.recommend_investigating_replenishment) {
    steps.push(
      `Forecasted demand (${compare.forecast_total_demand}) exceeds current available inventory ` +
        `(${compare.current_available_inventory}) over the next ${compare.horizon_days} day(s) -- investigate ` +
        "replenishment timing."
    );
  }
  if (steps.length === 0) {
    steps.push("No elevated risk signals for this SKU right now -- no action needed.");
  }
  return steps;
}

export function InventoryDetailDrawer({ sku, onClose }: { sku: string; onClose: () => void }) {
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

    // Deferred to a microtask (matching lib/useApi.ts's own pattern) so
    // setState doesn't run synchronously in the effect body.
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

  const warehouseColumns: DataTableColumn<{ warehouse_id: string; available: number; inbound_quantity: number; supplier_lead_time_days: number | null }>[] = [
    { key: "warehouse_id", header: "Warehouse", accessor: (r) => r.warehouse_id },
    { key: "available", header: "Available", align: "right", accessor: (r) => r.available },
    { key: "inbound", header: "Inbound Qty", align: "right", accessor: (r) => r.inbound_quantity },
    {
      key: "lead_time",
      header: "Supplier Lead Time (days)",
      align: "right",
      accessor: (r) => r.supplier_lead_time_days,
      render: (r) => r.supplier_lead_time_days ?? "Unknown",
    },
  ];

  const storeColumns: DataTableColumn<{ store_id: string; store_name: string; available_quantity: number }>[] = [
    { key: "store_id", header: "Store", accessor: (r) => `${r.store_name} (${r.store_id})` },
    { key: "qty", header: "Available Qty", align: "right", accessor: (r) => r.available_quantity },
  ];

  const openOrderColumns: DataTableColumn<{ order_id: string; order_status: string; quantity: number; promised_delivery_date: string | null }>[] = [
    { key: "order_id", header: "Order", accessor: (r) => r.order_id },
    { key: "status", header: "Status", accessor: (r) => r.order_status },
    { key: "qty", header: "Qty", align: "right", accessor: (r) => r.quantity },
    { key: "due", header: "Promised Delivery", accessor: (r) => r.promised_delivery_date ?? "Unknown" },
  ];

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-black/30" onClick={onClose} aria-hidden="true" />
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="inventory-detail-title"
        tabIndex={-1}
        className="relative z-50 flex h-full w-full max-w-2xl flex-col overflow-y-auto bg-[var(--ric-card-bg)] shadow-lg outline-none"
      >
        <div className="flex items-start justify-between gap-3 border-b border-[var(--ric-border)] px-5 py-4">
          <div>
            <h2 id="inventory-detail-title" className="text-sm font-semibold text-[var(--ric-text-primary)]">
              {sku} {analysis?.product?.product_name ? `-- ${analysis.product.product_name}` : ""}
            </h2>
            {analysis?.product?.category && (
              <p className="mt-0.5 text-xs text-[var(--ric-text-secondary)]">{analysis.product.category}</p>
            )}
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
          {loading && <LoadingState message="Loading SKU detail..." />}
          {error && <ErrorState message={error} />}

          {analysis && !loading && (
            <>
              <div className="flex flex-wrap items-center gap-2">
                <SeverityBadge value={analysis.estimated.risk_level} />
                {analysis.estimated.is_excess_inventory && <Badge label="Excess inventory" tone="warning" />}
                {analysis.data_as_of && (
                  <span className="text-xs text-[var(--ric-text-secondary)]">Data as of {analysis.data_as_of}</span>
                )}
              </div>

              {/* ---- Supporting data ---- */}
              <section>
                <h3 className="mb-2 text-sm font-semibold text-[var(--ric-text-primary)]">Supporting data</h3>
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                  <div className="rounded-lg border border-[var(--ric-border)] p-3">
                    <p className="text-xs text-[var(--ric-text-secondary)]">Store available</p>
                    <p className="mt-1 text-lg font-semibold text-[var(--ric-text-primary)]">
                      {analysis.observed.store_available_inventory}
                    </p>
                  </div>
                  <div className="rounded-lg border border-[var(--ric-border)] p-3">
                    <p className="text-xs text-[var(--ric-text-secondary)]">Avg daily sales (7d)</p>
                    <p className="mt-1 text-lg font-semibold text-[var(--ric-text-primary)]">
                      {analysis.estimated.avg_daily_sales_7d}
                    </p>
                  </div>
                  <div className="rounded-lg border border-[var(--ric-border)] p-3">
                    <p className="text-xs text-[var(--ric-text-secondary)]">Avg daily sales (30d)</p>
                    <p className="mt-1 text-lg font-semibold text-[var(--ric-text-primary)]">
                      {analysis.estimated.avg_daily_sales_30d}
                    </p>
                  </div>
                  <div className="rounded-lg border border-[var(--ric-border)] p-3">
                    <p className="text-xs text-[var(--ric-text-secondary)]">Days of inventory</p>
                    <p className="mt-1 text-lg font-semibold text-[var(--ric-text-primary)]">
                      {analysis.estimated.days_of_inventory ?? "Unavailable"}
                    </p>
                  </div>
                </div>

                <p className="mt-3 mb-1.5 text-xs font-medium text-[var(--ric-text-secondary)]">Inventory by store</p>
                <DataTable
                  columns={storeColumns}
                  rows={analysis.observed.store_breakdown}
                  rowKey={(r) => r.store_id}
                  emptyMessage="No store-level inventory for this SKU."
                />

                {analysis.observed.open_orders.length > 0 && (
                  <>
                    <p className="mt-3 mb-1.5 text-xs font-medium text-[var(--ric-text-secondary)]">
                      Open orders ({analysis.observed.open_orders.length})
                    </p>
                    <DataTable
                      columns={openOrderColumns}
                      rows={analysis.observed.open_orders}
                      rowKey={(r) => r.order_id}
                      emptyMessage="No open orders for this SKU."
                    />
                  </>
                )}
              </section>

              {/* ---- Demand trends / forecast results ---- */}
              <section>
                <div className="mb-2 flex items-center justify-between">
                  <h3 className="text-sm font-semibold text-[var(--ric-text-primary)]">
                    Demand trends &amp; forecast results
                  </h3>
                  <SelectFilter
                    label="Horizon"
                    value={String(horizonDays)}
                    options={HORIZON_OPTIONS}
                    onChange={(v) => setHorizonDays(Number(v))}
                  />
                </div>
                {salesHistory?.error && <ErrorState message={salesHistory.error} />}
                {salesHistory && !salesHistory.error && trendPoints.length === 0 && (
                  <EmptyState message="No confirmed sales history for this SKU." />
                )}
                {trendPoints.length > 0 && <DemandTrendChart points={trendPoints} />}

                {forecast && forecast.sufficient_data ? (
                  <p className="mt-2 text-sm text-[var(--ric-text-primary)]">
                    Total forecast demand ({forecast.horizon_days}d): <strong>{forecast.total_forecast_demand}</strong>{" "}
                    (method: {forecast.forecast_method})
                  </p>
                ) : forecast ? (
                  <EmptyState message={`Forecast unavailable: ${forecast.reason ?? "insufficient history"}`} />
                ) : null}

                {compare && compare.forecast_total_demand !== null && (
                  <div className="mt-3 rounded-lg border border-[var(--ric-border)] p-3 text-sm">
                    <p className="text-[var(--ric-text-primary)]">
                      Estimated demand gap vs. available inventory:{" "}
                      <strong>{compare.estimated_demand_gap_vs_store_available}</strong> (vs. available + inbound:{" "}
                      {compare.estimated_demand_gap_vs_available_plus_inbound})
                    </p>
                    <p className="mt-1 text-xs text-[var(--ric-text-secondary)]">{compare.disclaimer}</p>
                  </div>
                )}
              </section>

              {/* ---- Eligible warehouse inventory ---- */}
              <section>
                <h3 className="mb-2 text-sm font-semibold text-[var(--ric-text-primary)]">
                  Eligible warehouse inventory
                </h3>
                <p className="mb-1.5 text-xs text-[var(--ric-text-secondary)]">
                  Total available: {analysis.observed.warehouse.warehouse_available} -- total inbound:{" "}
                  {analysis.observed.warehouse.warehouse_inbound}
                </p>
                <DataTable
                  columns={warehouseColumns}
                  rows={analysis.observed.warehouse.by_warehouse}
                  rowKey={(r) => r.warehouse_id}
                  emptyMessage="No warehouse stock recorded for this SKU."
                />
              </section>

              {/* ---- Replenishment recommendation ---- */}
              <section>
                <h3 className="mb-2 text-sm font-semibold text-[var(--ric-text-primary)]">
                  Replenishment recommendation
                </h3>
                <div className="rounded-lg border border-[var(--ric-border)] p-3 text-sm">
                  <p className="text-[var(--ric-text-primary)]">
                    Suggested quantity: <strong>{analysis.recommendation.suggested_replenishment_quantity}</strong>
                  </p>
                  <p className="mt-1 text-xs text-[var(--ric-text-secondary)]">
                    {BASIS_LABELS[analysis.recommendation.basis] ?? analysis.recommendation.basis}
                  </p>
                  {analysis.recommendation.capped_by_warehouse_availability && (
                    <p className="mt-1 text-xs text-amber-700">Capped by available warehouse stock.</p>
                  )}
                </div>
              </section>

              {/* ---- Recommended next steps ---- */}
              <section>
                <h3 className="mb-2 text-sm font-semibold text-[var(--ric-text-primary)]">Recommended next steps</h3>
                <ul className="list-disc space-y-1 pl-5 text-sm text-[var(--ric-text-primary)]">
                  {buildNextSteps(analysis, compare).map((step, i) => (
                    <li key={i}>{step}</li>
                  ))}
                </ul>
                <p className="mt-2 text-xs text-[var(--ric-text-secondary)]">
                  All recommendations are read-only and require human approval.
                </p>
              </section>

              <EvidencePanel evidence={{ inventory: analysis, forecast, compare }} />
            </>
          )}
        </div>
      </div>
    </div>
  );
}
