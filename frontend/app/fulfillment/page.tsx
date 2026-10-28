"use client";

/**
 * Order Fulfillment Intelligence workspace -- every number here comes from
 * the existing Order Fulfillment Intelligence Agent
 * (order_fulfillment_agent/fulfillment_engine.py) via GET /fulfillment/at-risk,
 * /due-today, /inventory-shortages, /summary; no risk or feasibility logic
 * lives in this page.
 *
 * Two things this page is careful never to do, matching the backend:
 *  - Never imply an order is late just because it hasn't been delivered
 *    yet. Every risk badge and "due" label here is rendered from the
 *    engine's own risk_level/promised_date_passed/days_overdue/
 *    days_until_due fields -- an order with a future promised date and
 *    sufficient inventory is always shown as "low" risk.
 *  - Never invent carrier tracking or a delivery estimate. This dataset
 *    has no shipment/transit data; delivery feasibility is always shown as
 *    "unknown" (see OrderDetailDrawer), never guessed at from this table.
 */

import { useCallback, useMemo, useState } from "react";
import { Boxes, CalendarClock, PackageX, TriangleAlert } from "lucide-react";

import { getFulfillmentRiskSummary, getOrdersAtRisk, getOrdersDueToday, getOrdersWithInventoryShortages } from "@/lib/api";
import { useApi } from "@/lib/useApi";
import { orderSeverityKeys, severityLabel } from "@/lib/severity";
import type { FulfillmentPriorityItem } from "@/lib/types";
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
import { deliveryTimingLabel, OrderDetailDrawer } from "@/components/retail/OrderDetailDrawer";
import { SeverityBadge } from "@/components/retail/SeverityBadge";
import { StatusBadge } from "@/components/retail/StatusBadge";

const ALL = "__all__";

// Mirrors OrderFulfillmentEngine's own RISK_SEVERITY_ORDER exactly
// (order_fulfillment_agent/fulfillment_engine.py) -- "unable_to_assess"
// ranks above "low" there, since not knowing is treated as more urgent
// than a confirmed-healthy order.
const RISK_RANK: Record<string, number> = {
  critical: 0,
  high: 1,
  medium: 2,
  unable_to_assess: 3,
  low: 4,
  not_applicable: 5,
};

export default function FulfillmentPage() {
  const summary = useApi(() => getFulfillmentRiskSummary(), []);
  const atRisk = useApi(() => getOrdersAtRisk(), []);
  const dueToday = useApi(() => getOrdersDueToday(), []);
  const shortages = useApi(() => getOrdersWithInventoryShortages(), []);

  const [search, setSearch] = useState("");
  const [riskFilter, setRiskFilter] = useState(ALL);
  const [locationTypeFilter, setLocationTypeFilter] = useState(ALL);
  const [selectedOrderId, setSelectedOrderId] = useState<string | null>(null);

  const atRiskItems = useMemo(() => atRisk.data ?? [], [atRisk.data]);
  const dueTodayItems = useMemo(() => dueToday.data ?? [], [dueToday.data]);
  const shortageItems = useMemo(() => shortages.data ?? [], [shortages.data]);

  const riskOptions = useMemo(() => {
    const levels = new Set<string>();
    for (const list of [atRiskItems, dueTodayItems, shortageItems]) {
      for (const item of list) levels.add(item.risk_level);
    }
    return [
      { value: ALL, label: "All risk levels" },
      ...orderSeverityKeys([...levels]).map((level) => ({ value: level, label: severityLabel(level) })),
    ];
  }, [atRiskItems, dueTodayItems, shortageItems]);

  const locationTypeOptions = useMemo(() => {
    const types = new Set<string>();
    for (const list of [atRiskItems, dueTodayItems, shortageItems]) {
      for (const item of list) if (item.fulfillment_location_type) types.add(item.fulfillment_location_type);
    }
    return [
      { value: ALL, label: "All location types" },
      ...[...types].sort().map((t) => ({ value: t, label: t })),
    ];
  }, [atRiskItems, dueTodayItems, shortageItems]);

  const applyFilters = useCallback(
    (items: FulfillmentPriorityItem[]): FulfillmentPriorityItem[] => {
      const q = search.trim().toLowerCase();
      return items.filter((item) => {
        if (riskFilter !== ALL && item.risk_level !== riskFilter) return false;
        if (locationTypeFilter !== ALL && item.fulfillment_location_type !== locationTypeFilter) return false;
        if (
          q &&
          !item.order_id.toLowerCase().includes(q) &&
          !item.sku.toLowerCase().includes(q) &&
          !(item.customer_id ?? "").toLowerCase().includes(q)
        ) {
          return false;
        }
        return true;
      });
    },
    [search, riskFilter, locationTypeFilter]
  );

  const filteredAtRisk = useMemo(() => applyFilters(atRiskItems), [atRiskItems, applyFilters]);
  const filteredDueToday = useMemo(() => applyFilters(dueTodayItems), [dueTodayItems, applyFilters]);
  const filteredShortages = useMemo(() => applyFilters(shortageItems), [shortageItems, applyFilters]);

  const columns: DataTableColumn<FulfillmentPriorityItem>[] = [
    {
      key: "risk",
      header: "Risk",
      sortable: true,
      accessor: (r) => RISK_RANK[r.risk_level] ?? 99,
      render: (r) => <SeverityBadge value={r.risk_level} />,
    },
    { key: "order", header: "Order ID", sortable: true, accessor: (r) => r.order_id },
    { key: "customer", header: "Customer", sortable: true, accessor: (r) => r.customer_id ?? "Unknown" },
    { key: "sku", header: "SKU", sortable: true, accessor: (r) => r.sku },
    { key: "qty", header: "Qty", align: "right", sortable: true, accessor: (r) => r.quantity ?? null },
    {
      key: "status",
      header: "Status",
      accessor: (r) => r.order_status ?? "",
      render: (r) => (r.order_status ? <StatusBadge label={r.order_status} /> : "--"),
    },
    {
      key: "location",
      header: "Fulfillment Location",
      sortable: true,
      accessor: (r) => r.fulfillment_location ?? "Unknown",
      render: (r) =>
        `${r.fulfillment_location ?? "Unknown"}${
          r.fulfillment_location_type && r.fulfillment_location_type !== "unknown" ? ` (${r.fulfillment_location_type})` : ""
        }`,
    },
    {
      key: "promised",
      header: "Promised Delivery",
      sortable: true,
      accessor: (r) => r.promised_delivery_date ?? "",
      render: (r) => (
        <div>
          <p>{r.promised_delivery_date ?? "Not recorded"}</p>
          <p className="text-xs text-[var(--ric-text-secondary)]">{deliveryTimingLabel(r)}</p>
        </div>
      ),
    },
    {
      key: "inventory",
      header: "Inventory Sufficient?",
      align: "center",
      accessor: (r) =>
        r.inventory_readiness?.sufficient == null ? "Unknown" : r.inventory_readiness.sufficient ? "Yes" : "No",
      render: (r) =>
        r.inventory_readiness?.sufficient == null ? (
          "Unknown"
        ) : r.inventory_readiness.sufficient ? (
          <Badge label="Yes" tone="success" />
        ) : (
          <Badge label={`No (short ${r.inventory_readiness.shortfall ?? "?"})`} tone="danger" />
        ),
    },
    {
      key: "action",
      header: "",
      accessor: () => "",
      render: (r) => (
        <button
          type="button"
          onClick={() => setSelectedOrderId(r.order_id)}
          className="rounded-md border border-[var(--ric-border)] px-2.5 py-1 text-xs font-medium text-[var(--ric-primary)] hover:bg-[var(--ric-page-bg)]"
        >
          View order
        </button>
      ),
    },
  ];

  const anyLoading = summary.loading || atRisk.loading || dueToday.loading || shortages.loading;
  const anyError = summary.error || atRisk.error || dueToday.error || shortages.error;

  const criticalHigh = (summary.data?.risk_counts.critical ?? 0) + (summary.data?.risk_counts.high ?? 0);

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold text-[var(--ric-text-primary)]">Order Fulfillment</h1>
          <p className="mt-1 text-sm text-[var(--ric-text-secondary)]">
            Orders at risk, overdue orders, and inventory shortages from the Order Fulfillment Intelligence Agent.
            An order is never flagged late before its promised date has actually passed.
          </p>
        </div>
        <button
          type="button"
          onClick={() => {
            summary.refetch();
            atRisk.refetch();
            dueToday.refetch();
            shortages.refetch();
          }}
          className="flex items-center gap-1.5 rounded-md border border-[var(--ric-border)] bg-[var(--ric-card-bg)] px-3 py-1.5 text-sm font-medium text-[var(--ric-text-primary)] hover:bg-[var(--ric-page-bg)]"
        >
          Refresh data
        </button>
      </div>

      {anyLoading && <LoadingState message="Loading fulfillment data..." />}
      {anyError && <ErrorState message={anyError ?? "An unexpected error occurred."} />}

      {summary.data && (
        <>
          <DataFreshnessNote note={`Data as of ${summary.data.data_as_of}.`} />
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
            <KpiCard label="Total Open Orders" value={summary.data.total_open_orders} icon={Boxes} />
            <KpiCard label="Critical + High Risk" value={criticalHigh} icon={PackageX} />
            <KpiCard
              label="Unable to Assess"
              value={summary.data.risk_counts.unable_to_assess ?? 0}
              icon={TriangleAlert}
            />
            <KpiCard
              label="Inventory Shortages"
              value={summary.data.orders_with_inventory_shortages}
              icon={PackageX}
            />
            <KpiCard
              label="Due Today / Overdue"
              value={summary.data.orders_due_today_or_overdue}
              icon={CalendarClock}
            />
          </div>
        </>
      )}

      <Card>
        <CardHeader
          title="Filters"
          subtitle="Search and risk/location filters apply to all three tables below."
        />
        <FilterBar>
          <SearchInput value={search} onChange={setSearch} placeholder="Search order, SKU, or customer..." />
          <SelectFilter label="Risk level" value={riskFilter} options={riskOptions} onChange={setRiskFilter} />
          <SelectFilter
            label="Location type"
            value={locationTypeFilter}
            options={locationTypeOptions}
            onChange={setLocationTypeFilter}
          />
        </FilterBar>
      </Card>

      <Card>
        <CardHeader
          title="Orders at Risk"
          subtitle="Open orders classified critical, high, medium, or unable-to-assess -- excludes healthy (low-risk) orders."
        />
        <CardBody>
          <p className="mb-2 text-xs text-[var(--ric-text-secondary)]">
            Showing {filteredAtRisk.length} of {atRiskItems.length} order(s).
          </p>
          {atRisk.loading ? (
            <LoadingState message="Loading orders at risk..." />
          ) : filteredAtRisk.length === 0 ? (
            <EmptyState message="No orders at risk match the current filters." />
          ) : (
            <DataTable columns={columns} rows={filteredAtRisk} rowKey={(r) => r.order_id} emptyMessage="No orders at risk." />
          )}
        </CardBody>
      </Card>

      <Card>
        <CardHeader
          title="Due Today & Overdue Orders"
          subtitle="Open orders whose promised delivery date is today or has already passed. An order is only shown as overdue once that date has actually passed."
        />
        <CardBody>
          <p className="mb-2 text-xs text-[var(--ric-text-secondary)]">
            Showing {filteredDueToday.length} of {dueTodayItems.length} order(s).
          </p>
          {dueToday.loading ? (
            <LoadingState message="Loading due/overdue orders..." />
          ) : filteredDueToday.length === 0 ? (
            <EmptyState message="No orders are due today or overdue, or none match the current filters." />
          ) : (
            <DataTable
              columns={columns}
              rows={filteredDueToday}
              rowKey={(r) => r.order_id}
              emptyMessage="No due/overdue orders."
            />
          )}
        </CardBody>
      </Card>

      <Card>
        <CardHeader
          title="Orders Blocked by Inventory Shortages"
          subtitle="Open orders where eligible inventory at the assigned fulfillment location is below the required quantity."
        />
        <CardBody>
          <p className="mb-2 text-xs text-[var(--ric-text-secondary)]">
            Showing {filteredShortages.length} of {shortageItems.length} order(s).
          </p>
          {shortages.loading ? (
            <LoadingState message="Loading inventory-shortage orders..." />
          ) : filteredShortages.length === 0 ? (
            <EmptyState message="No orders are currently blocked by inventory shortages, or none match the current filters." />
          ) : (
            <DataTable
              columns={columns}
              rows={filteredShortages}
              rowKey={(r) => r.order_id}
              emptyMessage="No inventory-shortage orders."
            />
          )}
        </CardBody>
      </Card>

      <DisclaimerFooter text="All recommendations are read-only and require human approval. This agent never changes an order status, reassigns a fulfillment location, transfers stock, cancels an order, issues a refund, or sends any customer communication." />

      {selectedOrderId && <OrderDetailDrawer orderId={selectedOrderId} onClose={() => setSelectedOrderId(null)} />}
    </div>
  );
}
