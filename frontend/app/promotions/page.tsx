"use client";

/**
 * Promotion Intelligence workspace -- every number here comes from the
 * existing Promotion Intelligence Agent (promotion_agent/promotion_engine.py)
 * via GET /promotions/upcoming, /promotions/readiness, /promotions/demand-summary;
 * no readiness or uplift logic lives in this page. Product/category
 * metadata for the readiness table (which the engine doesn't attach
 * per-row) is read from GET /inventory/risks, the same cross-agent catalog
 * reuse already used on the Demand and Replenishment workspaces.
 *
 * This page is careful to keep two kinds of numbers visually and verbally
 * distinct, matching the backend's own design:
 *  - HISTORICAL OBSERVATIONS: a measured sales difference between an
 *    actual past promotional window and its preceding baseline window.
 *    Never claimed as proof the promotion caused the difference.
 *  - ESTIMATED PROMOTIONAL DEMAND: the Demand Forecasting Agent's baseline
 *    forecast, optionally adjusted by an uplift percentage from a real
 *    historical observation, an explicit what-if assumption, or left
 *    unknown. Always labeled "(estimate)" and tagged with its source.
 * See PromotionDetailDrawer for the full historical-vs-estimated
 * breakdown per SKU.
 *
 * Read-only throughout: nothing here (or in this backend) activates a
 * promotion, changes a price, places an order, or transfers inventory.
 */

import { useMemo, useState } from "react";
import { HelpCircle, PackageSearch, Tag, TrendingUp, TriangleAlert } from "lucide-react";

import {
  getInventoryRisks,
  getPromotionalDemandSummary,
  getPromotionReadiness,
  getUpcomingPromotions,
} from "@/lib/api";
import { useApi } from "@/lib/useApi";
import { orderSeverityKeys, severityLabel } from "@/lib/severity";
import type { PromotionReadinessItem, UpcomingPromotionItem } from "@/lib/types";
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
import { PromotionDetailDrawer } from "@/components/retail/PromotionDetailDrawer";
import { SeverityBadge } from "@/components/retail/SeverityBadge";

const ALL = "__all__";

const DAYS_AHEAD_OPTIONS = [
  { value: "7", label: "Next 7 days" },
  { value: "14", label: "Next 14 days" },
  { value: "30", label: "Next 30 days" },
  { value: "60", label: "Next 60 days" },
];

const UPLIFT_SOURCE_BADGE: Record<string, { label: string; tone: "info" | "warning" | "neutral" }> = {
  historical_uplift: { label: "Historical", tone: "info" },
  assumed_scenario: { label: "Assumed", tone: "warning" },
  unknown: { label: "Unknown", tone: "neutral" },
};

export default function PromotionsPage() {
  const [daysAhead, setDaysAhead] = useState(14);

  const summary = useApi(() => getPromotionalDemandSummary(), []);
  const upcoming = useApi(() => getUpcomingPromotions(daysAhead), [daysAhead]);
  const readiness = useApi(() => getPromotionReadiness(daysAhead), [daysAhead]);
  const catalog = useApi(() => getInventoryRisks(), []);

  const [search, setSearch] = useState("");
  const [channelFilter, setChannelFilter] = useState(ALL);
  const [readinessFilter, setReadinessFilter] = useState(ALL);
  const [selectedSku, setSelectedSku] = useState<string | null>(null);

  const upcomingItems = useMemo(() => upcoming.data ?? [], [upcoming.data]);
  const readinessItems = useMemo(() => readiness.data?.reports ?? [], [readiness.data]);
  const catalogItems = useMemo(() => catalog.data ?? [], [catalog.data]);

  const productMap = useMemo(() => {
    const map = new Map<string, { product_name: string; category: string }>();
    for (const item of catalogItems) {
      if (item.product) map.set(item.sku, { product_name: item.product.product_name, category: item.product.category });
    }
    return map;
  }, [catalogItems]);

  const promoMetaMap = useMemo(() => {
    const map = new Map<string, UpcomingPromotionItem>();
    for (const item of upcomingItems) map.set(item.promotion_id, item);
    return map;
  }, [upcomingItems]);

  const channelOptions = useMemo(() => {
    const channels = new Set<string>();
    for (const item of upcomingItems) channels.add(item.promotion_channel);
    return [
      { value: ALL, label: "All channels" },
      ...[...channels].sort().map((c) => ({ value: c, label: c })),
    ];
  }, [upcomingItems]);

  const readinessOptions = useMemo(() => {
    const statuses = new Set<string>();
    for (const item of readinessItems) statuses.add(item.readiness_status);
    return [
      { value: ALL, label: "All readiness statuses" },
      ...orderSeverityKeys([...statuses]).map((s) => ({ value: s, label: severityLabel(s) })),
    ];
  }, [readinessItems]);

  const filteredUpcoming = useMemo(() => {
    const q = search.trim().toLowerCase();
    return upcomingItems.filter((item) => {
      if (channelFilter !== ALL && item.promotion_channel !== channelFilter) return false;
      if (
        q &&
        !item.sku.toLowerCase().includes(q) &&
        !item.product_name.toLowerCase().includes(q) &&
        !item.promotion_name.toLowerCase().includes(q)
      ) {
        return false;
      }
      return true;
    });
  }, [upcomingItems, search, channelFilter]);

  const filteredReadiness = useMemo(() => {
    const q = search.trim().toLowerCase();
    return readinessItems.filter((item) => {
      if (readinessFilter !== ALL && item.readiness_status !== readinessFilter) return false;
      if (q) {
        const product = productMap.get(item.sku)?.product_name ?? "";
        const promoName = promoMetaMap.get(item.promotion_id)?.promotion_name ?? "";
        if (
          !item.sku.toLowerCase().includes(q) &&
          !product.toLowerCase().includes(q) &&
          !promoName.toLowerCase().includes(q) &&
          !item.promotion_id.toLowerCase().includes(q)
        ) {
          return false;
        }
      }
      return true;
    });
  }, [readinessItems, search, readinessFilter, productMap, promoMetaMap]);

  const upcomingColumns: DataTableColumn<UpcomingPromotionItem>[] = [
    { key: "sku", header: "SKU", sortable: true, accessor: (r) => r.sku },
    { key: "product", header: "Product", sortable: true, accessor: (r) => r.product_name },
    { key: "promo", header: "Promotion", sortable: true, accessor: (r) => r.promotion_name },
    { key: "discount", header: "Discount", align: "right", sortable: true, accessor: (r) => r.discount_percent },
    { key: "channel", header: "Channel", sortable: true, accessor: (r) => r.promotion_channel },
    { key: "start", header: "Start", sortable: true, accessor: (r) => r.start_date },
    { key: "end", header: "End", sortable: true, accessor: (r) => r.end_date },
    { key: "until", header: "Days Until Start", align: "right", sortable: true, accessor: (r) => r.days_until_start },
    { key: "duration", header: "Duration (days)", align: "right", sortable: true, accessor: (r) => r.duration_days },
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
          View readiness
        </button>
      ),
    },
  ];

  const readinessColumns: DataTableColumn<PromotionReadinessItem>[] = [
    {
      key: "status",
      header: "Readiness",
      sortable: true,
      accessor: (r) => r.readiness_status,
      render: (r) => <SeverityBadge value={r.readiness_status} />,
    },
    {
      key: "promo",
      header: "Promotion",
      sortable: true,
      accessor: (r) => promoMetaMap.get(r.promotion_id)?.promotion_name ?? r.promotion_id,
    },
    { key: "sku", header: "SKU", sortable: true, accessor: (r) => r.sku },
    {
      key: "product",
      header: "Product",
      sortable: true,
      accessor: (r) => productMap.get(r.sku)?.product_name ?? "Unknown",
    },
    { key: "dates", header: "Dates", accessor: (r) => `${r.start_date ?? "?"} to ${r.end_date ?? "?"}` },
    { key: "until", header: "Days Until Start", align: "right", sortable: true, accessor: (r) => r.days_until_start },
    {
      key: "baseline",
      header: "Baseline Demand (estimate)",
      align: "right",
      sortable: true,
      accessor: (r) => r.baseline_forecast_demand,
      render: (r) => r.baseline_forecast_demand ?? "Unavailable",
    },
    {
      key: "promoDemand",
      header: "Estimated Promotional Demand",
      align: "right",
      sortable: true,
      accessor: (r) => r.promotional_demand_estimate.estimated_total_demand,
      render: (r) => {
        const badge = UPLIFT_SOURCE_BADGE[r.promotional_demand_estimate.source] ?? UPLIFT_SOURCE_BADGE.unknown;
        return (
          <span className="inline-flex items-center gap-1.5">
            {r.promotional_demand_estimate.estimated_total_demand ?? "--"}
            <Badge label={badge.label} tone={badge.tone} />
          </span>
        );
      },
    },
    {
      key: "inventory",
      header: "Current Inventory",
      align: "right",
      sortable: true,
      accessor: (r) => r.observed?.current_available_inventory ?? null,
      render: (r) => r.observed?.current_available_inventory ?? "Unavailable",
    },
    {
      key: "warehouse",
      header: "Eligible Warehouse Stock",
      align: "right",
      sortable: true,
      accessor: (r) => r.observed?.warehouse_available_stock ?? null,
      render: (r) => r.observed?.warehouse_available_stock ?? "Unavailable",
    },
    {
      key: "inbound",
      header: "Eligible Inbound (within promo)",
      align: "right",
      sortable: true,
      accessor: (r) => r.observed?.known_inbound_stock_eligible_within_promotion ?? null,
      render: (r) => r.observed?.known_inbound_stock_eligible_within_promotion ?? "Unavailable",
    },
    {
      key: "gap",
      header: "Demand Gap",
      align: "right",
      sortable: true,
      accessor: (r) => r.demand_gap,
      render: (r) => r.demand_gap ?? "Unavailable",
    },
    {
      key: "risk",
      header: "Inventory Risk",
      accessor: (r) => r.inventory_agent_risk_level ?? "",
      render: (r) => (r.inventory_agent_risk_level ? <SeverityBadge value={r.inventory_agent_risk_level} /> : "--"),
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
          View details
        </button>
      ),
    },
  ];

  const anyLoading = summary.loading || upcoming.loading || readiness.loading || catalog.loading;
  const anyError = summary.error || upcoming.error || readiness.error || catalog.error;

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold text-[var(--ric-text-primary)]">Promotion Intelligence</h1>
          <p className="mt-1 text-sm text-[var(--ric-text-secondary)]">
            Upcoming promotions, inventory readiness, stockout risk, and replenishment feasibility from the
            Promotion Intelligence Agent. Estimated demand is always labeled and separated from historical
            observations.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <SelectFilter
            label="Window"
            value={String(daysAhead)}
            options={DAYS_AHEAD_OPTIONS}
            onChange={(v) => setDaysAhead(Number(v))}
          />
          <button
            type="button"
            onClick={() => {
              summary.refetch();
              upcoming.refetch();
              readiness.refetch();
              catalog.refetch();
            }}
            className="flex items-center gap-1.5 rounded-md border border-[var(--ric-border)] bg-[var(--ric-card-bg)] px-3 py-1.5 text-sm font-medium text-[var(--ric-text-primary)] hover:bg-[var(--ric-page-bg)]"
          >
            Refresh data
          </button>
        </div>
      </div>

      {anyLoading && <LoadingState message="Loading promotion data..." />}
      {anyError && <ErrorState message={anyError ?? "An unexpected error occurred."} />}

      {summary.data && (
        <>
          <DataFreshnessNote note={`Data as of ${summary.data.data_as_of}.`} />
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
            <KpiCard
              label="Promotions in Window"
              value={summary.data.upcoming_or_active_promotions_in_window}
              icon={Tag}
            />
            <KpiCard
              label="Insufficient Readiness"
              value={summary.data.readiness_counts.insufficient ?? 0}
              icon={TriangleAlert}
            />
            <KpiCard
              label="Cannot Determine"
              value={summary.data.readiness_counts.cannot_determine ?? 0}
              icon={HelpCircle}
            />
            <KpiCard
              label="Known Historical Uplift"
              value={summary.data.promotions_with_known_historical_uplift}
              icon={TrendingUp}
            />
            <KpiCard
              label="Products w/o Promotion History"
              value={summary.data.products_with_no_promotion_history}
              icon={PackageSearch}
            />
          </div>
        </>
      )}

      <Card>
        <CardHeader title="Search" subtitle="Applies to both tables below by SKU, product, or promotion name." />
        <FilterBar>
          <SearchInput value={search} onChange={setSearch} placeholder="Search SKU, product, or promotion..." />
        </FilterBar>
      </Card>

      <Card>
        <CardHeader
          title="Upcoming Promotions"
          subtitle={`Promotions starting within the selected window, with the product each applies to. Promotions in this dataset are scoped to a single SKU and channel -- never a multi-product campaign.`}
        />
        <FilterBar>
          <SelectFilter label="Channel" value={channelFilter} options={channelOptions} onChange={setChannelFilter} />
        </FilterBar>
        <CardBody>
          <p className="mb-2 text-xs text-[var(--ric-text-secondary)]">
            Showing {filteredUpcoming.length} of {upcomingItems.length} upcoming promotion(s).
          </p>
          {upcoming.loading ? (
            <LoadingState message="Loading upcoming promotions..." />
          ) : filteredUpcoming.length === 0 ? (
            <EmptyState message="No upcoming promotions match the current filters." />
          ) : (
            <DataTable
              columns={upcomingColumns}
              rows={filteredUpcoming}
              rowKey={(r) => r.promotion_id}
              emptyMessage="No upcoming promotions."
            />
          )}
        </CardBody>
      </Card>

      <Card>
        <CardHeader
          title="Promotion Readiness"
          subtitle="Inventory readiness for every upcoming or active promotion in the selected window -- stockout risk, eligible warehouse stock, replenishment feasibility, and estimated promotional demand (clearly separated from historical observations)."
        />
        <FilterBar>
          <SelectFilter
            label="Readiness"
            value={readinessFilter}
            options={readinessOptions}
            onChange={setReadinessFilter}
          />
        </FilterBar>
        <CardBody>
          <p className="mb-2 text-xs text-[var(--ric-text-secondary)]">
            Showing {filteredReadiness.length} of {readinessItems.length} promotion/SKU readiness assessment(s).
          </p>
          {readiness.loading ? (
            <LoadingState message="Loading promotion readiness..." />
          ) : filteredReadiness.length === 0 ? (
            <EmptyState message="No readiness assessments match the current filters." />
          ) : (
            <DataTable
              columns={readinessColumns}
              rows={filteredReadiness}
              rowKey={(r) => `${r.promotion_id}-${r.sku}`}
              emptyMessage="No readiness assessments."
            />
          )}
        </CardBody>
      </Card>

      <DisclaimerFooter text="All recommendations are read-only and require human approval. No promotion is activated, no price is changed, no order is placed, and no inventory is transferred automatically." />

      {selectedSku && <PromotionDetailDrawer sku={selectedSku} onClose={() => setSelectedSku(null)} />}
    </div>
  );
}
