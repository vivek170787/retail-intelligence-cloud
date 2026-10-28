"use client";

/**
 * Replenishment workspace -- every number here comes from the existing
 * Inventory Intelligence Agent (inventory_agent/risk_engine.py) via
 * GET /inventory/replenishment, /inventory/summary, /inventory/risks, and
 * /inventory/stores/{store_id}; no replenishment logic lives in this page.
 * There is no separate Replenishment agent -- this is the same engine that
 * backs the Inventory Intelligence workspace, filtered and framed around
 * the replenishment recommendation itself.
 *
 * "Store-Level Shortages" below calls GET /inventory/stores/{store_id} once
 * per known store (the engine's own per-store method, called over the
 * catalog-wide store list since the REST route requires a store_id path
 * param) -- a genuinely per-store risk assessment, distinct from the
 * "Product Replenishment Recommendations" table, whose suggested quantity
 * is computed from inventory and sales velocity combined across all
 * stores (see InventoryRiskEngine's documented design). The store filter
 * on the product table only narrows which SKUs are stocked at that store;
 * it does not imply a store-level suggested quantity.
 *
 * Strictly read-only: nothing on this page (or in this backend) creates a
 * purchase order, transfers stock, or changes any operational record.
 */

import { useMemo, useState } from "react";
import { Boxes, PackageX, Store, TriangleAlert, Warehouse } from "lucide-react";

import { getInventoryReplenishment, getInventoryRisks, getInventorySummary, getStoreInventoryRisks } from "@/lib/api";
import { useApi } from "@/lib/useApi";
import { orderSeverityKeys, severityLabel } from "@/lib/severity";
import type { InventoryRiskItem, StoreShortageItem } from "@/lib/types";
import { DataTable, type DataTableColumn } from "@/components/ui/DataTable";
import { FilterBar } from "@/components/ui/FilterBar";
import { SearchInput } from "@/components/ui/SearchInput";
import { SelectFilter } from "@/components/ui/SelectFilter";
import { Badge } from "@/components/ui/Badge";
import { Card, CardBody, CardHeader } from "@/components/retail/Card";
import { DataFreshnessNote } from "@/components/retail/DataFreshnessNote";
import { DisclaimerFooter } from "@/components/retail/DisclaimerFooter";
import { EmptyState } from "@/components/retail/EmptyState";
import { ErrorState } from "@/components/retail/ErrorState";
import { KpiCard } from "@/components/retail/KpiCard";
import { LoadingState } from "@/components/retail/LoadingState";
import { ReplenishmentDetailDrawer } from "@/components/retail/ReplenishmentDetailDrawer";
import { SeverityBadge } from "@/components/retail/SeverityBadge";

const ALL = "__all__";

// Only critical/high/medium can ever come back from either endpoint used on
// this page (InventoryRiskEngine filters out low/unknown for replenishment
// and store-shortage results), so this covers every value actually seen.
const RISK_RANK: Record<string, number> = { critical: 0, high: 1, medium: 2 };

export default function ReplenishmentPage() {
  const summary = useApi(() => getInventorySummary(), []);
  const replenishment = useApi(() => getInventoryReplenishment(), []);
  const catalog = useApi(() => getInventoryRisks(), []);

  const [search, setSearch] = useState("");
  const [categoryFilter, setCategoryFilter] = useState(ALL);
  const [storeFilter, setStoreFilter] = useState(ALL);
  const [riskFilter, setRiskFilter] = useState(ALL);
  const [selectedSku, setSelectedSku] = useState<string | null>(null);

  const items = useMemo(() => replenishment.data ?? [], [replenishment.data]);
  const catalogItems = useMemo(() => catalog.data ?? [], [catalog.data]);

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

  const storeIdsKey = storeOptions.map((o) => o.value).join(",");
  const storeShortages = useApi(
    () =>
      storeOptions.length === 0
        ? Promise.resolve<StoreShortageItem[]>([])
        : Promise.all(storeOptions.map((o) => getStoreInventoryRisks(o.value))).then((lists) => lists.flat()),
    [storeIdsKey]
  );

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
    for (const item of storeShortages.data ?? []) levels.add(item.estimated.risk_level);
    return [
      { value: ALL, label: "All risk levels" },
      ...orderSeverityKeys([...levels]).map((level) => ({ value: level, label: severityLabel(level) })),
    ];
  }, [items, storeShortages.data]);

  const filteredItems = useMemo(() => {
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
  }, [items, search, categoryFilter, storeFilter, riskFilter]);

  const filteredStoreShortages = useMemo(() => {
    const q = search.trim().toLowerCase();
    return (storeShortages.data ?? [])
      .filter((item) => {
        if (riskFilter !== ALL && item.estimated.risk_level !== riskFilter) return false;
        if (storeFilter !== ALL && item.store_id !== storeFilter) return false;
        if (q && !item.sku.toLowerCase().includes(q) && !item.product_name.toLowerCase().includes(q)) return false;
        return true;
      })
      .sort((a, b) => (RISK_RANK[a.estimated.risk_level] ?? 99) - (RISK_RANK[b.estimated.risk_level] ?? 99));
  }, [storeShortages.data, search, storeFilter, riskFilter]);

  const cappedCount = useMemo(
    () => items.filter((i) => i.recommendation.capped_by_warehouse_availability).length,
    [items]
  );
  const storesWithShortagesCount = useMemo(
    () => new Set((storeShortages.data ?? []).map((s) => s.store_id)).size,
    [storeShortages.data]
  );
  const criticalHighCount = useMemo(
    () => items.filter((i) => i.estimated.risk_level === "critical" || i.estimated.risk_level === "high").length,
    [items]
  );
  const targetCoverageDays = catalogItems[0]?.settings_used?.replenishment_target_days;

  const openDetail = (sku: string) => setSelectedSku(sku);

  const productColumns: DataTableColumn<InventoryRiskItem>[] = [
    { key: "sku", header: "SKU", sortable: true, accessor: (r) => r.sku },
    { key: "product", header: "Product", sortable: true, accessor: (r) => r.product?.product_name ?? "Unknown" },
    { key: "category", header: "Category", sortable: true, accessor: (r) => r.product?.category ?? "Unknown" },
    {
      key: "risk",
      header: "Risk Level",
      sortable: true,
      accessor: (r) => RISK_RANK[r.estimated.risk_level] ?? 99,
      render: (r) => <SeverityBadge value={r.estimated.risk_level} />,
    },
    {
      key: "current",
      header: "Current Inventory (all stores)",
      align: "right",
      sortable: true,
      accessor: (r) => r.observed.store_available_inventory,
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
      key: "warehouse",
      header: "Eligible Warehouse Stock",
      align: "right",
      sortable: true,
      accessor: (r) => r.observed.warehouse.warehouse_available,
    },
    {
      key: "inbound",
      header: "Eligible Inbound",
      align: "right",
      sortable: true,
      accessor: (r) => r.observed.warehouse.warehouse_inbound,
    },
    {
      key: "suggested",
      header: "Suggested Qty",
      align: "right",
      sortable: true,
      accessor: (r) => r.recommendation.suggested_replenishment_quantity,
    },
    {
      key: "capped",
      header: "Capped by Warehouse?",
      align: "center",
      accessor: (r) => (r.recommendation.capped_by_warehouse_availability ? "Yes" : "No"),
      render: (r) =>
        r.recommendation.capped_by_warehouse_availability ? <Badge label="Capped" tone="warning" dot /> : "No",
    },
    {
      key: "action",
      header: "",
      accessor: () => "",
      render: (r) => (
        <button
          type="button"
          onClick={() => openDetail(r.sku)}
          className="rounded-md border border-[var(--ric-border)] px-2.5 py-1 text-xs font-medium text-[var(--ric-primary)] hover:bg-[var(--ric-page-bg)]"
        >
          View recommendation
        </button>
      ),
    },
  ];

  const storeShortageColumns: DataTableColumn<StoreShortageItem>[] = [
    { key: "store", header: "Store", sortable: true, accessor: (r) => `${r.store_name} (${r.store_id})` },
    { key: "sku", header: "SKU", sortable: true, accessor: (r) => r.sku },
    { key: "product", header: "Product", sortable: true, accessor: (r) => r.product_name },
    {
      key: "risk",
      header: "Risk Level",
      sortable: true,
      accessor: (r) => RISK_RANK[r.estimated.risk_level] ?? 99,
      render: (r) => <SeverityBadge value={r.estimated.risk_level} />,
    },
    {
      key: "available",
      header: "Available Qty (this store)",
      align: "right",
      sortable: true,
      accessor: (r) => r.observed.available_quantity,
    },
    {
      key: "velocity",
      header: "Avg Daily Sales (7d, this store)",
      align: "right",
      sortable: true,
      accessor: (r) => r.estimated.avg_daily_sales_7d,
    },
    {
      key: "days",
      header: "Days of Inventory (this store)",
      align: "right",
      sortable: true,
      accessor: (r) => r.estimated.days_of_inventory ?? Number.POSITIVE_INFINITY,
      render: (r) => r.estimated.days_of_inventory ?? "Unknown",
    },
    {
      key: "action",
      header: "",
      accessor: () => "",
      render: (r) => (
        <button
          type="button"
          onClick={() => openDetail(r.sku)}
          className="rounded-md border border-[var(--ric-border)] px-2.5 py-1 text-xs font-medium text-[var(--ric-primary)] hover:bg-[var(--ric-page-bg)]"
        >
          View recommendation
        </button>
      ),
    },
  ];

  const anyLoading = summary.loading || replenishment.loading || catalog.loading;
  const anyError = summary.error || replenishment.error || catalog.error;

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold text-[var(--ric-text-primary)]">Replenishment</h1>
          <p className="mt-1 text-sm text-[var(--ric-text-secondary)]">
            Stores and products needing replenishment, suggested quantities, and the inventory data behind them --
            from the Inventory Intelligence Agent. Every recommendation here is read-only.
          </p>
        </div>
        <button
          type="button"
          onClick={() => {
            summary.refetch();
            replenishment.refetch();
            catalog.refetch();
            storeShortages.refetch();
          }}
          className="flex items-center gap-1.5 rounded-md border border-[var(--ric-border)] bg-[var(--ric-card-bg)] px-3 py-1.5 text-sm font-medium text-[var(--ric-text-primary)] hover:bg-[var(--ric-page-bg)]"
        >
          Refresh data
        </button>
      </div>

      {anyLoading && <LoadingState message="Loading replenishment data..." />}
      {anyError && <ErrorState message={anyError ?? "An unexpected error occurred."} />}

      {summary.data && (
        <>
          <DataFreshnessNote
            note={summary.data.data_as_of ? `Data as of ${summary.data.data_as_of}.` : "Data freshness unknown."}
          />
          {targetCoverageDays != null && (
            <p className="text-xs text-[var(--ric-text-secondary)]">
              Suggested quantities target {targetCoverageDays} day(s) of sales coverage. This system does not
              configure a separate safety-stock buffer -- see each SKU&apos;s detail view for the full rationale.
            </p>
          )}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
            <KpiCard label="Products Needing Replenishment" value={summary.data.products_needing_replenishment} icon={Boxes} />
            <KpiCard label="Critical + High Risk" value={criticalHighCount} icon={PackageX} />
            <KpiCard label="Capped by Warehouse Availability" value={cappedCount} icon={Warehouse} />
            <KpiCard label="Stores with Shortages" value={storesWithShortagesCount} icon={Store} />
            <KpiCard label="Open Orders at Risk" value={summary.data.open_orders_at_risk_count} icon={TriangleAlert} />
          </div>
        </>
      )}

      <Card>
        <CardHeader
          title="Filters"
          subtitle="Search and store/risk filters apply to both tables below; Category applies to Product Replenishment Recommendations only."
        />
        <FilterBar>
          <SearchInput value={search} onChange={setSearch} placeholder="Search SKU or product name..." />
          <SelectFilter
            label="Store"
            value={storeFilter}
            options={[{ value: ALL, label: "All stores" }, ...storeOptions]}
            onChange={setStoreFilter}
          />
          <SelectFilter label="Risk level" value={riskFilter} options={riskOptions} onChange={setRiskFilter} />
        </FilterBar>
      </Card>

      <Card>
        <CardHeader
          title="Store-Level Shortages"
          subtitle="Per-store critical/high/medium risk SKUs, computed independently at each store (not combined across stores) -- the Inventory Intelligence Agent's own per-store method."
        />
        <CardBody>
          <p className="mb-2 text-xs text-[var(--ric-text-secondary)]">
            Showing {filteredStoreShortages.length} of {(storeShortages.data ?? []).length} store/SKU shortage(s).
          </p>
          {storeShortages.loading ? (
            <LoadingState message="Loading store-level shortages..." />
          ) : filteredStoreShortages.length === 0 ? (
            <EmptyState message="No store-level shortages match the current filters." />
          ) : (
            <DataTable
              columns={storeShortageColumns}
              rows={filteredStoreShortages}
              rowKey={(r) => `${r.store_id}-${r.sku}`}
              emptyMessage="No store-level shortages."
            />
          )}
        </CardBody>
      </Card>

      <Card>
        <CardHeader
          title="Product Replenishment Recommendations"
          subtitle="Every SKU with a positive suggested replenishment quantity, most severe risk first -- computed from inventory and sales velocity combined across all stores, never exceeding eligible warehouse stock."
        />
        <FilterBar>
          <SelectFilter
            label="Category"
            value={categoryFilter}
            options={categoryOptions}
            onChange={setCategoryFilter}
          />
        </FilterBar>
        <CardBody>
          <p className="mb-2 text-xs text-[var(--ric-text-secondary)]">
            Showing {filteredItems.length} of {items.length} SKU(s).
          </p>
          {replenishment.loading ? (
            <LoadingState message="Loading replenishment recommendations..." />
          ) : filteredItems.length === 0 ? (
            <EmptyState message="No SKUs currently need replenishment, or none match the current filters." />
          ) : (
            <DataTable
              columns={productColumns}
              rows={filteredItems}
              rowKey={(r) => r.sku}
              emptyMessage="No SKUs match the current filters."
            />
          )}
        </CardBody>
      </Card>

      <DisclaimerFooter text="All recommendations are read-only and require human approval. No purchase order, stock transfer, inventory record, or other operational record is created or changed by this application." />

      {selectedSku && <ReplenishmentDetailDrawer sku={selectedSku} onClose={() => setSelectedSku(null)} />}
    </div>
  );
}
