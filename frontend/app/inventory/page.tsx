"use client";

/**
 * Inventory Intelligence workspace -- every number here comes from the
 * existing InventoryRiskEngine (inventory_agent/risk_engine.py) via
 * GET /inventory/risks and /inventory/summary; no business logic lives
 * in this page, matching every other workspace in this app. Filtering
 * (store/category/risk level/search) is client-side over the already-
 * fetched catalog-wide risk list -- the dataset is small (the full
 * product catalog), so no new paginated/filtered backend route is
 * needed. Selecting a row opens InventoryDetailDrawer, which fetches the
 * per-SKU detail (including the Demand Forecasting Agent's forecast and
 * cross-check) on demand.
 *
 * Store filtering is partial, by design: InventoryRiskEngine computes
 * sales velocity / days-of-inventory / risk level across all stores
 * combined, not per store (see risk_engine.py's own documented design).
 * Selecting a store narrows the table to SKUs stocked at that store and
 * swaps in that store's own available quantity, but the velocity/risk
 * columns stay catalog-wide -- labeled as such in the filter bar caption
 * rather than implying a store-level risk calculation that doesn't exist.
 */

import { useMemo, useState } from "react";
import { Boxes, PackageCheck, PackageX, RefreshCw, TriangleAlert } from "lucide-react";

import { getInventoryRisks, getInventorySummary } from "@/lib/api";
import { useApi } from "@/lib/useApi";
import { orderSeverityKeys, severityLabel } from "@/lib/severity";
import type { InventoryRiskItem } from "@/lib/types";
import { DataTable, type DataTableColumn } from "@/components/ui/DataTable";
import { FilterBar } from "@/components/ui/FilterBar";
import { SearchInput } from "@/components/ui/SearchInput";
import { SelectFilter } from "@/components/ui/SelectFilter";
import { Card, CardBody, CardHeader } from "@/components/retail/Card";
import { DataFreshnessNote } from "@/components/retail/DataFreshnessNote";
import { DisclaimerFooter } from "@/components/retail/DisclaimerFooter";
import { EmptyState } from "@/components/retail/EmptyState";
import { ErrorState } from "@/components/retail/ErrorState";
import { InventoryDetailDrawer } from "@/components/retail/InventoryDetailDrawer";
import { KpiCard } from "@/components/retail/KpiCard";
import { LoadingState } from "@/components/retail/LoadingState";
import { SeverityBadge } from "@/components/retail/SeverityBadge";

const ALL = "__all__";

export default function InventoryPage() {
  const risks = useApi(() => getInventoryRisks(), []);
  const summary = useApi(() => getInventorySummary(), []);

  const [search, setSearch] = useState("");
  const [storeFilter, setStoreFilter] = useState(ALL);
  const [categoryFilter, setCategoryFilter] = useState(ALL);
  const [riskFilter, setRiskFilter] = useState(ALL);
  const [selectedSku, setSelectedSku] = useState<string | null>(null);

  const items = useMemo(() => risks.data ?? [], [risks.data]);

  const storeOptions = useMemo(() => {
    const byId = new Map<string, string>();
    for (const item of items) {
      for (const s of item.observed.store_breakdown) byId.set(s.store_id, s.store_name);
    }
    return [
      { value: ALL, label: "All stores" },
      ...[...byId.entries()].sort((a, b) => a[0].localeCompare(b[0])).map(([id, name]) => ({
        value: id,
        label: `${name} (${id})`,
      })),
    ];
  }, [items]);

  const categoryOptions = useMemo(() => {
    const categories = new Set<string>();
    for (const item of items) if (item.product?.category) categories.add(item.product.category);
    return [
      { value: ALL, label: "All categories" },
      ...[...categories].sort().map((c) => ({ value: c, label: c })),
    ];
  }, [items]);

  const riskOptions = useMemo(() => {
    const levels = new Set<string>();
    for (const item of items) levels.add(item.estimated.risk_level);
    return [
      { value: ALL, label: "All risk levels" },
      ...orderSeverityKeys([...levels]).map((level) => ({ value: level, label: severityLabel(level) })),
    ];
  }, [items]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return items.filter((item) => {
      if (riskFilter !== ALL && item.estimated.risk_level !== riskFilter) return false;
      if (categoryFilter !== ALL && item.product?.category !== categoryFilter) return false;
      if (storeFilter !== ALL && !item.observed.store_breakdown.some((s) => s.store_id === storeFilter)) {
        return false;
      }
      if (q && !item.sku.toLowerCase().includes(q) && !(item.product?.product_name ?? "").toLowerCase().includes(q)) {
        return false;
      }
      return true;
    });
  }, [items, search, storeFilter, categoryFilter, riskFilter]);

  function storeQuantity(item: InventoryRiskItem): number | null {
    if (storeFilter === ALL) return null;
    return item.observed.store_breakdown.find((s) => s.store_id === storeFilter)?.available_quantity ?? 0;
  }

  const columns: DataTableColumn<InventoryRiskItem>[] = [
    { key: "sku", header: "SKU", sortable: true, accessor: (r) => r.sku },
    { key: "product", header: "Product", sortable: true, accessor: (r) => r.product?.product_name ?? "Unknown" },
    { key: "category", header: "Category", sortable: true, accessor: (r) => r.product?.category ?? "Unknown" },
    {
      key: "risk",
      header: "Risk Level",
      sortable: true,
      accessor: (r) => r.estimated.risk_level,
      render: (r) => <SeverityBadge value={r.estimated.risk_level} />,
    },
    {
      key: "stock",
      header: storeFilter === ALL ? "Store Available (all stores)" : "Store Available (selected store)",
      align: "right",
      sortable: true,
      accessor: (r) => storeQuantity(r) ?? r.observed.store_available_inventory,
    },
    {
      key: "velocity",
      header: "Avg Daily Sales (7d)",
      align: "right",
      sortable: true,
      accessor: (r) => r.estimated.avg_daily_sales_7d,
    },
    {
      key: "days",
      header: "Days of Inventory",
      align: "right",
      sortable: true,
      accessor: (r) => r.estimated.days_of_inventory ?? Number.POSITIVE_INFINITY,
      render: (r) => r.estimated.days_of_inventory ?? "Unknown",
    },
    {
      key: "excess",
      header: "Excess",
      align: "center",
      accessor: (r) => (r.estimated.is_excess_inventory ? "Yes" : "No"),
    },
    {
      key: "warehouse",
      header: "Warehouse Available",
      align: "right",
      sortable: true,
      accessor: (r) => r.observed.warehouse.warehouse_available,
    },
    {
      key: "replenish",
      header: "Suggested Replenishment",
      align: "right",
      sortable: true,
      accessor: (r) => r.recommendation.suggested_replenishment_quantity,
    },
    {
      key: "action",
      header: "",
      accessor: () => "",
      render: (r) => (
        <button
          type="button"
          onClick={() => setSelectedSku(r.sku)}
          className="rounded-lg border border-[var(--ric-border)] px-2.5 py-1 text-xs font-medium text-[var(--ric-primary)] hover:bg-[var(--ric-page-bg)]"
        >
          View details
        </button>
      ),
    },
  ];

  const replenishmentItems = useMemo(
    () => items.filter((i) => i.recommendation.suggested_replenishment_quantity > 0),
    [items]
  );

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold text-[var(--ric-text-primary)]">Inventory Intelligence</h1>
          <p className="mt-1 text-sm text-[var(--ric-text-secondary)]">
            Stock, sales velocity, stockout/excess risk, warehouse availability, and replenishment recommendations
            from the Inventory Intelligence Agent.
          </p>
        </div>
        <button
          type="button"
          onClick={() => {
            risks.refetch();
            summary.refetch();
          }}
          className="flex items-center gap-1.5 rounded-lg border border-[var(--ric-border)] bg-[var(--ric-card-bg)] px-3 py-1.5 text-sm font-medium text-[var(--ric-text-primary)] hover:bg-[var(--ric-page-bg)]"
        >
          <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
          Refresh data
        </button>
      </div>

      {risks.loading && <LoadingState message="Loading inventory risk data..." />}
      {risks.error && <ErrorState message={risks.error} />}

      {summary.data && (
        <>
          <DataFreshnessNote
            note={summary.data.data_as_of ? `Data as of ${summary.data.data_as_of}.` : "Data freshness unknown."}
          />

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <KpiCard label="Total Products" value={summary.data.total_products} icon={Boxes} />
            <KpiCard
              label="Critical + High Stockout Risk"
              value={(summary.data.risk_level_counts.critical ?? 0) + (summary.data.risk_level_counts.high ?? 0)}
              icon={PackageX}
            />
            <KpiCard
              label="Products with Excess Inventory"
              value={summary.data.products_with_excess_inventory}
              icon={PackageCheck}
            />
            <KpiCard
              label="Open Orders at Risk"
              value={summary.data.open_orders_at_risk_count}
              icon={TriangleAlert}
            />
          </div>
        </>
      )}

      {items.length > 0 && (
        <Card>
          <CardHeader
            title="Inventory by SKU and Store"
            subtitle={
              storeFilter === ALL
                ? "Catalog-wide view. Select a store below to see that store's available quantity; sales velocity, days of inventory, and risk level are computed across all stores combined (see InventoryRiskEngine's documented design)."
                : "Store Available now reflects the selected store's own quantity. Sales velocity, days of inventory, and risk level remain catalog-wide (combined across all stores) -- this agent does not compute a per-store risk classification."
            }
          />
          <FilterBar>
            <SearchInput value={search} onChange={setSearch} placeholder="Search SKU or product name..." />
            <SelectFilter label="Store" value={storeFilter} options={storeOptions} onChange={setStoreFilter} />
            <SelectFilter
              label="Category"
              value={categoryFilter}
              options={categoryOptions}
              onChange={setCategoryFilter}
            />
            <SelectFilter label="Risk level" value={riskFilter} options={riskOptions} onChange={setRiskFilter} />
          </FilterBar>
          <CardBody>
            <p className="mb-2 text-xs text-[var(--ric-text-secondary)]">
              Showing {filtered.length} of {items.length} SKU(s).
            </p>
            <DataTable
              columns={columns}
              rows={filtered}
              rowKey={(r) => r.sku}
              emptyMessage="No SKUs match the current filters."
            />
          </CardBody>
        </Card>
      )}

      <Card>
        <CardHeader
          title="Replenishment Recommendations"
          subtitle="SKUs with a positive suggested replenishment quantity, from the Inventory Intelligence Agent -- never exceeding eligible warehouse stock."
        />
        <CardBody>
          {risks.loading ? (
            <LoadingState message="Loading..." />
          ) : replenishmentItems.length === 0 ? (
            <EmptyState message="No SKUs currently need replenishment." />
          ) : (
            <DataTable
              columns={columns.filter((c) => c.key !== "action")}
              rows={replenishmentItems}
              rowKey={(r) => r.sku}
            />
          )}
        </CardBody>
      </Card>

      <DisclaimerFooter />

      {selectedSku && <InventoryDetailDrawer sku={selectedSku} onClose={() => setSelectedSku(null)} />}
    </div>
  );
}
