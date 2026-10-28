"use client";

/**
 * Demand Forecasting workspace -- every number here comes from the
 * existing DemandForecastEngine (demand_forecasting_agent/forecasting_engine.py)
 * via GET /demand/summary, /demand/top-forecasted, /demand/spikes,
 * /demand/declines; no forecasting logic lives in this page, matching
 * every other workspace in this app. The SKU/product/category/store
 * catalog is read from GET /inventory/risks (the Inventory Intelligence
 * Agent's own full-catalog listing) purely for its product and store
 * metadata -- the same cross-agent reuse the backend itself already does
 * (DemandForecastEngine.compare_forecast_with_inventory reuses
 * InventoryRiskEngine) -- rather than re-deriving a product catalog here.
 *
 * Every forecast total on this page is a flat-rate weighted-moving-average
 * estimate, labeled "(estimate)" wherever it's shown, never asserted as a
 * guaranteed figure. Forecast accuracy is never claimed from this page;
 * the only accuracy numbers shown are the backtest's measured MAE/WAPE/
 * bias against real held-out actuals (see ForecastErrorMetrics), and only
 * when the engine reports enough history to run that backtest.
 *
 * Store filtering here is catalog-presence filtering only (which SKUs are
 * stocked at a store) -- the catalog-wide ranking and spike/decline
 * detection stay combined across all stores, since the engine methods
 * backing them don't compute a per-store version. A true store-level
 * forecast is only available after opening a SKU's detail drawer, which
 * calls forecast_demand(sku, store_id=...) directly.
 */

import { useMemo, useState } from "react";
import { PackageSearch, TrendingDown, TrendingUp, Gauge, Boxes } from "lucide-react";

import { getDemandDeclines, getDemandSpikes, getDemandSummary, getInventoryRisks, getTopForecastedProducts } from "@/lib/api";
import { useApi } from "@/lib/useApi";
import type { DemandChangeItem, DemandForecastResult, InventoryRiskItem } from "@/lib/types";
import { DataTable, type DataTableColumn } from "@/components/ui/DataTable";
import { FilterBar } from "@/components/ui/FilterBar";
import { SearchInput } from "@/components/ui/SearchInput";
import { SelectFilter } from "@/components/ui/SelectFilter";
import { Badge } from "@/components/ui/Badge";
import { Card, CardBody, CardHeader } from "@/components/retail/Card";
import { DemandDetailDrawer } from "@/components/retail/DemandDetailDrawer";
import { DisclaimerFooter } from "@/components/retail/DisclaimerFooter";
import { EmptyState } from "@/components/retail/EmptyState";
import { ErrorState } from "@/components/retail/ErrorState";
import { KpiCard } from "@/components/retail/KpiCard";
import { LoadingState } from "@/components/retail/LoadingState";

const ALL = "__all__";
const HORIZON_OPTIONS = [
  { value: "7", label: "7 days" },
  { value: "14", label: "14 days" },
  { value: "30", label: "30 days" },
];

interface CatalogRow {
  sku: string;
  product_name: string;
  category: string;
  store_breakdown: InventoryRiskItem["observed"]["store_breakdown"];
  forecast: DemandForecastResult | null;
}

function changeTone(item: DemandChangeItem): "danger" | "warning" {
  return item.percent_change >= 0 ? "danger" : "warning";
}

export default function DemandPage() {
  const [horizonDays, setHorizonDays] = useState(7);

  const summary = useApi(() => getDemandSummary(), []);
  const spikes = useApi(() => getDemandSpikes(), []);
  const declines = useApi(() => getDemandDeclines(), []);
  const catalog = useApi(() => getInventoryRisks(), []);
  // High limit so the ranking covers every product the engine judges to
  // have sufficient history, not just a "top 10" sample.
  const topForecasted = useApi(() => getTopForecastedProducts(horizonDays, 1000), [horizonDays]);

  const [search, setSearch] = useState("");
  const [categoryFilter, setCategoryFilter] = useState(ALL);
  const [storeFilter, setStoreFilter] = useState(ALL);
  const [selectedSku, setSelectedSku] = useState<string | null>(null);

  const catalogItems = useMemo(() => catalog.data ?? [], [catalog.data]);
  const forecastResults = useMemo(() => topForecasted.data ?? [], [topForecasted.data]);

  const storeOptions = useMemo(() => {
    const byId = new Map<string, string>();
    for (const item of catalogItems) {
      for (const s of item.observed.store_breakdown) byId.set(s.store_id, s.store_name);
    }
    return [...byId.entries()].sort((a, b) => a[0].localeCompare(b[0])).map(([id, name]) => ({
      value: id,
      label: `${name} (${id})`,
    }));
  }, [catalogItems]);

  const categoryOptions = useMemo(() => {
    const categories = new Set<string>();
    for (const item of catalogItems) if (item.product?.category) categories.add(item.product.category);
    return [
      { value: ALL, label: "All categories" },
      ...[...categories].sort().map((c) => ({ value: c, label: c })),
    ];
  }, [catalogItems]);

  const rows: CatalogRow[] = useMemo(() => {
    const forecastBySku = new Map(forecastResults.map((f) => [f.sku, f]));
    return catalogItems.map((item) => ({
      sku: item.sku,
      product_name: item.product?.product_name ?? "Unknown",
      category: item.product?.category ?? "Unknown",
      store_breakdown: item.observed.store_breakdown,
      forecast: forecastBySku.get(item.sku) ?? null,
    }));
  }, [catalogItems, forecastResults]);

  const filteredRows = useMemo(() => {
    const q = search.trim().toLowerCase();
    return rows.filter((row) => {
      if (categoryFilter !== ALL && row.category !== categoryFilter) return false;
      if (storeFilter !== ALL && !row.store_breakdown.some((s) => s.store_id === storeFilter)) return false;
      if (q && !row.sku.toLowerCase().includes(q) && !row.product_name.toLowerCase().includes(q)) return false;
      return true;
    });
  }, [rows, search, categoryFilter, storeFilter]);

  const columns: DataTableColumn<CatalogRow>[] = [
    { key: "sku", header: "SKU", sortable: true, accessor: (r) => r.sku },
    { key: "product", header: "Product", sortable: true, accessor: (r) => r.product_name },
    { key: "category", header: "Category", sortable: true, accessor: (r) => r.category },
    {
      key: "historical",
      header: "Avg Daily Sales (historical)",
      align: "right",
      sortable: true,
      // Number.NEGATIVE_INFINITY (not null) so missing data sorts to the
      // bottom under the table's default descending sort, matching this
      // column's "highest first" intent regardless of toggle state.
      accessor: (r) => r.forecast?.historical_avg_daily_sales ?? Number.NEGATIVE_INFINITY,
      render: (r) => r.forecast?.historical_avg_daily_sales ?? "Insufficient history",
    },
    {
      key: "forecast",
      header: `Forecast Total, ${horizonDays}d (estimate)`,
      align: "right",
      sortable: true,
      accessor: (r) =>
        r.forecast?.sufficient_data ? r.forecast.total_forecast_demand ?? Number.NEGATIVE_INFINITY : Number.NEGATIVE_INFINITY,
      render: (r) =>
        r.forecast?.sufficient_data ? r.forecast.total_forecast_demand : <span className="text-[var(--ric-text-secondary)]">--</span>,
    },
    {
      key: "method",
      header: "Method",
      accessor: (r) => r.forecast?.forecast_method ?? "",
      render: (r) => r.forecast?.forecast_method ?? "--",
    },
    {
      key: "sufficient",
      header: "Data Sufficient?",
      align: "center",
      accessor: (r) => (r.forecast?.sufficient_data ? "Yes" : "No"),
      render: (r) =>
        r.forecast?.sufficient_data ? (
          <Badge label="Yes" tone="success" />
        ) : (
          <Badge label="No" tone="neutral" />
        ),
    },
    {
      key: "action",
      header: "",
      accessor: () => "",
      render: (r) => (
        <button
          type="button"
          onClick={() => setSelectedSku(r.sku)}
          className="rounded-md border border-[var(--ric-border)] px-2.5 py-1 text-xs font-medium text-[var(--ric-primary)] hover:bg-[var(--ric-page-bg)]"
        >
          View forecast
        </button>
      ),
    },
  ];

  const changeColumns = (): DataTableColumn<DemandChangeItem>[] => [
    { key: "sku", header: "SKU", sortable: true, accessor: (r) => r.sku },
    { key: "product", header: "Product", sortable: true, accessor: (r) => r.product_name },
    {
      key: "change",
      header: "% Change (recent vs. baseline)",
      align: "right",
      sortable: true,
      accessor: (r) => r.percent_change,
      render: (r) => (
        <Badge
          label={`${r.percent_change > 0 ? "+" : ""}${r.percent_change}%`}
          tone={changeTone(r)}
          dot
        />
      ),
    },
    {
      key: "recent",
      header: "Recent Avg / Day",
      align: "right",
      sortable: true,
      accessor: (r) => r.recent_window_avg,
    },
    {
      key: "baseline",
      header: "Baseline Avg / Day",
      align: "right",
      sortable: true,
      accessor: (r) => r.baseline_window_avg,
    },
    {
      key: "periods",
      header: "Recent Period",
      accessor: (r) => r.recent_period.join(" to "),
    },
    {
      key: "promo",
      header: "Promotion Overlap",
      align: "center",
      accessor: (r) => (r.promotion_overlap ? "Yes" : "No"),
      render: (r) => (r.promotion_overlap ? <Badge label="Yes" tone="info" /> : "No"),
    },
    {
      key: "caveat",
      header: "Data Gap",
      align: "center",
      accessor: (r) => (r.data_quality_caveat ? "Yes" : "No"),
      render: (r) => (r.data_quality_caveat ? <Badge label="Caveat" tone="warning" /> : "No"),
    },
    {
      key: "action",
      header: "",
      accessor: () => "",
      render: (r) => (
        <button
          type="button"
          onClick={() => setSelectedSku(r.sku)}
          className="rounded-md border border-[var(--ric-border)] px-2.5 py-1 text-xs font-medium text-[var(--ric-primary)] hover:bg-[var(--ric-page-bg)]"
        >
          View forecast
        </button>
      ),
    },
  ];

  const anyLoading = summary.loading || spikes.loading || declines.loading || catalog.loading || topForecasted.loading;
  const anyError = summary.error || catalog.error;

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold text-[var(--ric-text-primary)]">Demand Forecasting</h1>
          <p className="mt-1 text-sm text-[var(--ric-text-secondary)]">
            Historical sales, forecast demand, demand spikes/declines, and backtested error metrics from the Demand
            Forecasting Agent. Every forecast total is an estimate, not a guarantee.
          </p>
        </div>
        <button
          type="button"
          onClick={() => {
            summary.refetch();
            spikes.refetch();
            declines.refetch();
            catalog.refetch();
            topForecasted.refetch();
          }}
          className="flex items-center gap-1.5 rounded-md border border-[var(--ric-border)] bg-[var(--ric-card-bg)] px-3 py-1.5 text-sm font-medium text-[var(--ric-text-primary)] hover:bg-[var(--ric-page-bg)]"
        >
          Refresh data
        </button>
      </div>

      {anyLoading && <LoadingState message="Loading demand data..." />}
      {anyError && <ErrorState message={anyError ?? "An unexpected error occurred."} />}

      {summary.data && (
        <>
          <p className="text-xs text-[var(--ric-text-secondary)]">
            Default forecast horizon for these totals: {summary.data.settings_used.default_horizon_days} day(s).
            Use the horizon selector below to recompute the product ranking at a different horizon.
          </p>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
            <KpiCard label="Total Products" value={summary.data.total_products} icon={Boxes} />
            <KpiCard
              label="Insufficient History"
              value={summary.data.products_with_insufficient_history}
              icon={PackageSearch}
            />
            <KpiCard
              label={`Total Forecast Demand, ${summary.data.settings_used.default_horizon_days}d (estimate)`}
              value={summary.data.total_forecast_demand_next_horizon}
              icon={Gauge}
            />
            <KpiCard label="Demand Spikes" value={summary.data.products_with_demand_spike} icon={TrendingUp} />
            <KpiCard
              label="Declining Demand"
              value={summary.data.products_with_declining_demand}
              icon={TrendingDown}
            />
          </div>
        </>
      )}

      <Card>
        <CardHeader
          title="Products & Forecasts"
          subtitle={`Ranked by total forecast demand (estimate) over the next ${horizonDays} day(s), weighted-moving-average baseline, combined across all stores. The store filter below narrows which SKUs are stocked at that store -- it does not recompute a store-level forecast (open a SKU's detail to do that).`}
        />
        <FilterBar>
          <SearchInput value={search} onChange={setSearch} placeholder="Search SKU or product name..." />
          <SelectFilter
            label="Category"
            value={categoryFilter}
            options={categoryOptions}
            onChange={setCategoryFilter}
          />
          <SelectFilter
            label="Store"
            value={storeFilter}
            options={[{ value: ALL, label: "All stores" }, ...storeOptions]}
            onChange={setStoreFilter}
          />
          <SelectFilter
            label="Forecast horizon"
            value={String(horizonDays)}
            options={HORIZON_OPTIONS}
            onChange={(v) => setHorizonDays(Number(v))}
          />
        </FilterBar>
        <CardBody>
          <p className="mb-2 text-xs text-[var(--ric-text-secondary)]">
            Showing {filteredRows.length} of {rows.length} SKU(s).
          </p>
          <DataTable
            columns={columns}
            rows={filteredRows}
            rowKey={(r) => r.sku}
            loading={catalog.loading || topForecasted.loading}
            emptyMessage="No SKUs match the current filters."
            defaultSortKey="forecast"
            defaultSortDirection="desc"
          />
        </CardBody>
      </Card>

      <Card>
        <CardHeader
          title="Demand Spikes"
          subtitle={`SKUs whose recent ${spikes.data?.[0]?.recent_window_days ?? 7}-day average sales rose sharply vs. the preceding baseline window. A promotion overlap, if flagged, may or may not explain the change -- it is not asserted as the cause.`}
        />
        <CardBody>
          {spikes.loading ? (
            <LoadingState message="Loading..." />
          ) : (spikes.data ?? []).length === 0 ? (
            <EmptyState message="No demand spikes detected right now." />
          ) : (
            <DataTable
              columns={changeColumns()}
              rows={spikes.data!}
              rowKey={(r) => r.sku}
              defaultSortKey="change"
              defaultSortDirection="desc"
            />
          )}
        </CardBody>
      </Card>

      <Card>
        <CardHeader
          title="Declining Demand"
          subtitle="SKUs whose recent average sales dropped sharply vs. the preceding baseline window."
        />
        <CardBody>
          {declines.loading ? (
            <LoadingState message="Loading..." />
          ) : (declines.data ?? []).length === 0 ? (
            <EmptyState message="No declining-demand SKUs detected right now." />
          ) : (
            <DataTable
              columns={changeColumns()}
              rows={declines.data!}
              rowKey={(r) => r.sku}
              defaultSortKey="change"
              defaultSortDirection="asc"
            />
          )}
        </CardBody>
      </Card>

      <DisclaimerFooter />

      {selectedSku && (
        <DemandDetailDrawer
          sku={selectedSku}
          initialHorizonDays={horizonDays}
          storeOptions={storeOptions}
          onClose={() => setSelectedSku(null)}
        />
      )}
    </div>
  );
}
