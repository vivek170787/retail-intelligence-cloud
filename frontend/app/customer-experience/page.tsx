"use client";

/**
 * Customer Experience Intelligence workspace -- every number here comes
 * from the existing Customer Experience Intelligence Agent
 * (customer_experience_agent/cx_engine.py) via GET
 * /customer-experience/impact-risks, /recovery-recommendations, /summary;
 * no risk, problem-type, or recovery logic lives in this page. That agent
 * is itself a thin layer over OrderFulfillmentEngine -- every fulfillment
 * fact shown here (promised date, inventory readiness) is reused verbatim.
 *
 * customer_id is always a synthetic CUST-NNNNN identifier -- this dataset
 * has no name, email, phone, or address field anywhere, and this page
 * never fabricates, looks up, or displays anything beyond that id.
 *
 * "Problem type" distinguishes a CONFIRMED problem (promised date already
 * passed -- a fact) from a PREDICTED risk (inventory short but the date
 * hasn't passed yet -- a forward-looking concern, not yet a fact). This
 * page keeps that distinction visible everywhere a severity appears.
 *
 * Read-only throughout: nothing here (or in this backend) messages a
 * customer, cancels an order, issues a refund, or promises a delivery
 * date. Every recovery-action field is either "human review may be
 * warranted" (never a specific action -- there is no policy dataset) or a
 * plain read-only recommendation string.
 */

import { useMemo, useState } from "react";
import { AlertOctagon, HelpCircle, TrendingDown, TriangleAlert, Users } from "lucide-react";

import { getCustomerExperienceSummary, getCustomerImpactRisks, getServiceRecoveryRecommendations } from "@/lib/api";
import { useApi } from "@/lib/useApi";
import { orderSeverityKeys, severityLabel } from "@/lib/severity";
import type { CustomerImpactRiskItem } from "@/lib/types";
import { DataTable, type DataTableColumn } from "@/components/ui/DataTable";
import { FilterBar } from "@/components/ui/FilterBar";
import { SearchInput } from "@/components/ui/SearchInput";
import { SelectFilter } from "@/components/ui/SelectFilter";
import { Badge, type BadgeTone } from "@/components/ui/Badge";
import { Card, CardBody, CardHeader } from "@/components/retail/Card";
import { CustomerExperienceDetailDrawer } from "@/components/retail/CustomerExperienceDetailDrawer";
import { DisclaimerFooter } from "@/components/retail/DisclaimerFooter";
import { EmptyState } from "@/components/retail/EmptyState";
import { ErrorState } from "@/components/retail/ErrorState";
import { KpiCard } from "@/components/retail/KpiCard";
import { LoadingState } from "@/components/retail/LoadingState";
import { deliveryTimingLabel } from "@/components/retail/OrderDetailDrawer";
import { SeverityBadge } from "@/components/retail/SeverityBadge";

const ALL = "__all__";

const PROBLEM_TYPE_LABELS: Record<string, { label: string; tone: BadgeTone }> = {
  confirmed: { label: "Confirmed problem", tone: "danger" },
  predicted: { label: "Predicted risk", tone: "warning" },
  unknown: { label: "Unknown -- insufficient data", tone: "neutral" },
  none: { label: "No risk identified", tone: "success" },
  not_applicable: { label: "Not applicable", tone: "neutral" },
};

// Mirrors CustomerExperienceEngine's own SEVERITY_ORDER exactly
// (customer_experience_agent/cx_engine.py).
const SEVERITY_RANK: Record<string, number> = {
  critical: 0,
  high: 1,
  medium: 2,
  unable_to_assess: 3,
  low: 4,
  not_applicable: 5,
};

export default function CustomerExperiencePage() {
  const summary = useApi(() => getCustomerExperienceSummary(), []);
  const impactRisks = useApi(() => getCustomerImpactRisks(), []);
  const recovery = useApi(() => getServiceRecoveryRecommendations(), []);

  const [search, setSearch] = useState("");
  const [severityFilter, setSeverityFilter] = useState(ALL);
  const [problemTypeFilter, setProblemTypeFilter] = useState(ALL);
  const [humanReviewFilter, setHumanReviewFilter] = useState(ALL);
  const [selectedOrderId, setSelectedOrderId] = useState<string | null>(null);

  const items = useMemo(() => impactRisks.data ?? [], [impactRisks.data]);

  const needsHumanReviewCount = useMemo(
    () => items.filter((i) => i.human_reviewed_recovery_action?.suggested).length,
    [items]
  );

  const severityOptions = useMemo(() => {
    const levels = new Set<string>();
    for (const item of items) levels.add(item.severity);
    return [
      { value: ALL, label: "All severities" },
      ...orderSeverityKeys([...levels]).map((level) => ({ value: level, label: severityLabel(level) })),
    ];
  }, [items]);

  const problemTypeOptions = useMemo(() => {
    const types = new Set<string>();
    for (const item of items) if (item.problem_type) types.add(item.problem_type);
    return [
      { value: ALL, label: "All problem types" },
      ...[...types].map((t) => ({ value: t, label: PROBLEM_TYPE_LABELS[t]?.label ?? t })),
    ];
  }, [items]);

  const filteredItems = useMemo(() => {
    const q = search.trim().toLowerCase();
    return items.filter((item) => {
      if (severityFilter !== ALL && item.severity !== severityFilter) return false;
      if (problemTypeFilter !== ALL && item.problem_type !== problemTypeFilter) return false;
      if (humanReviewFilter === "yes" && !item.human_reviewed_recovery_action?.suggested) return false;
      if (humanReviewFilter === "no" && item.human_reviewed_recovery_action?.suggested) return false;
      if (
        q &&
        !item.order_id.toLowerCase().includes(q) &&
        !(item.sku ?? "").toLowerCase().includes(q) &&
        !(item.customer_id ?? "").toLowerCase().includes(q)
      ) {
        return false;
      }
      return true;
    });
  }, [items, search, severityFilter, problemTypeFilter, humanReviewFilter]);

  const columns: DataTableColumn<CustomerImpactRiskItem>[] = [
    {
      key: "severity",
      header: "Severity",
      sortable: true,
      accessor: (r) => SEVERITY_RANK[r.severity] ?? 99,
      render: (r) => <SeverityBadge value={r.severity} />,
    },
    {
      key: "problem",
      header: "Problem Type",
      sortable: true,
      accessor: (r) => r.problem_type ?? "",
      render: (r) => {
        const pt = r.problem_type ? PROBLEM_TYPE_LABELS[r.problem_type] : undefined;
        return pt ? <Badge label={pt.label} tone={pt.tone} /> : "--";
      },
    },
    { key: "order", header: "Order ID", sortable: true, accessor: (r) => r.order_id },
    { key: "customer", header: "Customer (synthetic ID)", sortable: true, accessor: (r) => r.customer_id ?? "Unknown" },
    { key: "sku", header: "SKU", sortable: true, accessor: (r) => r.sku ?? "Unknown" },
    {
      key: "location",
      header: "Fulfillment Location",
      sortable: true,
      accessor: (r) => r.fulfillment_location ?? "Unknown",
    },
    {
      key: "promised",
      header: "Promised Delivery",
      accessor: (r) => r.fulfillment_assessment?.promised_delivery_date ?? "",
      render: (r) => (
        <div>
          <p>{r.fulfillment_assessment?.promised_delivery_date ?? "Not recorded"}</p>
          {r.fulfillment_assessment && (
            <p className="text-xs text-[var(--ric-text-secondary)]">{deliveryTimingLabel(r.fulfillment_assessment)}</p>
          )}
        </div>
      ),
    },
    {
      key: "cancellation",
      header: "Cancellation Risk",
      align: "center",
      accessor: (r) => (r.potential_cancellation_risk?.flagged ? "Yes" : "No"),
      render: (r) =>
        r.potential_cancellation_risk?.flagged ? <Badge label="Flagged" tone="danger" /> : "No",
    },
    {
      key: "marketplace",
      header: "Marketplace Issue",
      align: "center",
      accessor: (r) => (r.marketplace_context?.any_availability_issue ? "Yes" : "No"),
      render: (r) =>
        r.marketplace_context?.any_availability_issue ? <Badge label="Issue" tone="warning" /> : "No",
    },
    {
      key: "human",
      header: "Needs Human Review",
      align: "center",
      accessor: (r) => (r.human_reviewed_recovery_action?.suggested ? "Yes" : "No"),
      render: (r) =>
        r.human_reviewed_recovery_action?.suggested ? <Badge label="Review needed" tone="warning" /> : "No",
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
          View details
        </button>
      ),
    },
  ];

  const anyLoading = summary.loading || impactRisks.loading || recovery.loading;
  const anyError = summary.error || impactRisks.error || recovery.error;

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold text-[var(--ric-text-primary)]">Customer Experience</h1>
          <p className="mt-1 text-sm text-[var(--ric-text-secondary)]">
            Orders with potential delivery problems and inventory-related customer risk, from the Customer
            Experience Intelligence Agent. Customer identifiers are synthetic; no other personal information
            exists in this dataset.
          </p>
        </div>
        <button
          type="button"
          onClick={() => {
            summary.refetch();
            impactRisks.refetch();
            recovery.refetch();
          }}
          className="flex items-center gap-1.5 rounded-md border border-[var(--ric-border)] bg-[var(--ric-card-bg)] px-3 py-1.5 text-sm font-medium text-[var(--ric-text-primary)] hover:bg-[var(--ric-page-bg)]"
        >
          Refresh data
        </button>
      </div>

      {anyLoading && <LoadingState message="Loading customer experience data..." />}
      {anyError && <ErrorState message={anyError ?? "An unexpected error occurred."} />}

      {summary.data && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
          <KpiCard label="Total Customer Impact Risks" value={summary.data.total_customer_impact_risks} icon={Users} />
          <KpiCard
            label="Confirmed Problems"
            value={summary.data.problem_type_counts.confirmed ?? 0}
            icon={AlertOctagon}
          />
          <KpiCard
            label="Predicted Risks"
            value={summary.data.problem_type_counts.predicted ?? 0}
            icon={TriangleAlert}
          />
          <KpiCard
            label="Potential Cancellation Risk"
            value={summary.data.orders_with_potential_cancellation_risk}
            icon={TrendingDown}
          />
          <KpiCard label="Needs Human Review" value={needsHumanReviewCount} icon={HelpCircle} />
        </div>
      )}

      <Card>
        <CardHeader
          title="Orders with Customer Impact"
          subtitle="Open orders with a confirmed or predicted fulfillment problem, inventory-related risk, or marketplace availability issue. A problem is only shown as confirmed once the promised date has actually passed -- otherwise it is labeled a predicted risk."
        />
        <FilterBar>
          <SearchInput value={search} onChange={setSearch} placeholder="Search order, SKU, or customer ID..." />
          <SelectFilter label="Severity" value={severityFilter} options={severityOptions} onChange={setSeverityFilter} />
          <SelectFilter
            label="Problem type"
            value={problemTypeFilter}
            options={problemTypeOptions}
            onChange={setProblemTypeFilter}
          />
          <SelectFilter
            label="Human review"
            value={humanReviewFilter}
            options={[
              { value: ALL, label: "All" },
              { value: "yes", label: "Needs human review" },
              { value: "no", label: "No review flagged" },
            ]}
            onChange={setHumanReviewFilter}
          />
        </FilterBar>
        <CardBody>
          <p className="mb-2 text-xs text-[var(--ric-text-secondary)]">
            Showing {filteredItems.length} of {items.length} order(s).
          </p>
          {impactRisks.loading ? (
            <LoadingState message="Loading customer impact risks..." />
          ) : filteredItems.length === 0 ? (
            <EmptyState message="No customer impact risks match the current filters." />
          ) : (
            <DataTable
              columns={columns}
              rows={filteredItems}
              rowKey={(r) => r.order_id}
              emptyMessage="No customer impact risks."
            />
          )}
        </CardBody>
      </Card>

      <Card>
        <CardHeader
          title="Recommended Service Recovery Actions"
          subtitle="Read-only, human-reviewed recommendations only -- no message is sent, no order is cancelled, no refund is issued, and no delivery date is promised automatically."
        />
        <CardBody>
          {recovery.loading ? (
            <LoadingState message="Loading recovery recommendations..." />
          ) : !recovery.data || recovery.data.orders.length === 0 ? (
            <EmptyState message="No service recovery recommendations right now." />
          ) : (
            <>
              <p className="mb-2 text-xs text-[var(--ric-text-secondary)]">
                {recovery.data.total_orders_with_recommendations} order(s) with at least one recommendation.
              </p>
              <div className="mb-4 flex flex-wrap gap-2">
                {Object.entries(recovery.data.action_counts).map(([action, count]) => (
                  <Badge key={action} label={`${action} (${count})`} tone="neutral" />
                ))}
              </div>
              <ul className="space-y-2">
                {recovery.data.orders.map((o) => (
                  <li key={o.order_id} className="rounded-md border border-[var(--ric-border)] p-3 text-sm">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p className="font-medium text-[var(--ric-text-primary)]">
                        {o.order_id} {o.sku ? `-- ${o.sku}` : ""}
                      </p>
                      <div className="flex items-center gap-2">
                        <SeverityBadge value={o.severity} />
                        <button
                          type="button"
                          onClick={() => setSelectedOrderId(o.order_id)}
                          className="rounded-md border border-[var(--ric-border)] px-2.5 py-1 text-xs font-medium text-[var(--ric-primary)] hover:bg-[var(--ric-page-bg)]"
                        >
                          View details
                        </button>
                      </div>
                    </div>
                    <ul className="mt-2 list-disc space-y-0.5 pl-5 text-[var(--ric-text-primary)]">
                      {o.recommended_actions.map((a, i) => (
                        <li key={i}>{a}</li>
                      ))}
                    </ul>
                  </li>
                ))}
              </ul>
            </>
          )}
        </CardBody>
      </Card>

      <DisclaimerFooter text="All recommendations are read-only and require human approval. This agent never changes an order, cancels or refunds anything, transfers inventory, or sends any customer communication or external API call." />

      {selectedOrderId && (
        <CustomerExperienceDetailDrawer orderId={selectedOrderId} onClose={() => setSelectedOrderId(null)} />
      )}
    </div>
  );
}
