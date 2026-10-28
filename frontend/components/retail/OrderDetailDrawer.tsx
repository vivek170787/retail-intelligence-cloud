"use client";

/**
 * Order-level fulfillment drill-down. Everything comes from one call --
 * GET /fulfillment/orders/{order_id} (OrderFulfillmentEngine.analyze_order_fulfillment)
 * -- including alternative fulfillment candidates, which the engine only
 * attaches when risk is medium or higher. No recomputation happens here.
 *
 * Two things this component is careful never to do, matching the backend:
 *  - Never imply an order is late because it simply hasn't been delivered
 *    yet. risk_level, promised_date_passed, days_overdue, and
 *    days_until_due are rendered exactly as returned -- an order with a
 *    future promised date and sufficient inventory is shown as "low" risk,
 *    full stop.
 *  - Never invent carrier tracking, a delivery estimate, or an outbound
 *    transit time. delivery_feasibility.status is always rendered as
 *    "Unknown" with the backend's own reason text, and every alternative
 *    fulfillment candidate is shown with its real feasibility label
 *    ("candidate requires validation" or "insufficient stock") -- never
 *    relabeled as "feasible" or given an invented ETA.
 */

import { useEffect, useRef, useState } from "react";
import { X } from "lucide-react";

import { ApiError, getOrderFulfillmentAnalysis } from "@/lib/api";
import type { AlternativeFulfillmentCandidate, FulfillmentPriorityItem } from "@/lib/types";
import { Badge } from "@/components/ui/Badge";
import { DataTable, type DataTableColumn } from "@/components/ui/DataTable";
import { DataGapsPanel } from "@/components/retail/DataGapsPanel";
import { EmptyState } from "@/components/retail/EmptyState";
import { ErrorState } from "@/components/retail/ErrorState";
import { EvidencePanel } from "@/components/retail/EvidencePanel";
import { LoadingState } from "@/components/retail/LoadingState";
import { SeverityBadge } from "@/components/retail/SeverityBadge";
import { StatusBadge } from "@/components/retail/StatusBadge";

export function deliveryTimingLabel(report: FulfillmentPriorityItem): string {
  if (report.promised_date_missing) return "No promised delivery date recorded.";
  if (report.promised_date_passed) return `Overdue by ${report.days_overdue} day(s).`;
  if (report.days_until_due === 0) return "Due today.";
  if (report.days_until_due != null) return `Due in ${report.days_until_due} day(s).`;
  return "Timing unknown.";
}

export function OrderDetailDrawer({ orderId, onClose }: { orderId: string; onClose: () => void }) {
  const [report, setReport] = useState<FulfillmentPriorityItem | null>(null);
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

    getOrderFulfillmentAnalysis(orderId)
      .then((r) => {
        if (cancelled) return;
        setReport(r);
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
  }, [orderId]);

  useEffect(() => {
    panelRef.current?.focus();
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  const alternativeColumns: DataTableColumn<AlternativeFulfillmentCandidate>[] = [
    { key: "location", header: "Location", accessor: (r) => `${r.location_id} (${r.location_type})` },
    { key: "available", header: "Eligible Available", align: "right", accessor: (r) => r.eligible_available },
    {
      key: "sufficient",
      header: "Sufficient Stock?",
      align: "center",
      accessor: (r) => (r.sufficient_stock ? "Yes" : r.sufficient_stock === false ? "No" : "Unknown"),
      render: (r) =>
        r.sufficient_stock == null ? (
          "Unknown"
        ) : r.sufficient_stock ? (
          <Badge label="Yes" tone="success" />
        ) : (
          <Badge label="No" tone="neutral" />
        ),
    },
    {
      key: "leadtime",
      header: "Inbound Lead Time",
      align: "right",
      accessor: (r) => r.lead_time_days,
      render: (r) => (r.lead_time_known ? `${r.lead_time_days} day(s)` : "Unknown"),
    },
    {
      key: "feasibility",
      header: "Feasibility",
      accessor: (r) => r.feasibility,
      render: (r) => (
        <Badge
          label={r.feasibility === "candidate_requires_validation" ? "Candidate -- requires validation" : "Insufficient stock"}
          tone={r.feasibility === "candidate_requires_validation" ? "info" : "neutral"}
        />
      ),
    },
  ];

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-black/30" onClick={onClose} aria-hidden="true" />
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="order-detail-title"
        tabIndex={-1}
        className="relative z-50 flex h-full w-full max-w-2xl flex-col overflow-y-auto bg-[var(--ric-card-bg)] shadow-lg outline-none"
      >
        <div className="flex items-start justify-between gap-3 border-b border-[var(--ric-border)] px-5 py-4">
          <div>
            <h2 id="order-detail-title" className="text-sm font-semibold text-[var(--ric-text-primary)]">
              {orderId} {report?.sku ? `-- ${report.sku}` : ""}
            </h2>
            <p className="mt-0.5 text-xs text-[var(--ric-text-secondary)]">Order fulfillment detail</p>
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
          {loading && <LoadingState message="Loading order detail..." />}
          {error && <ErrorState message={error} />}

          {report && !loading && report.order_found === false && (
            <EmptyState message={report.note ?? `No order found with order_id ${orderId}.`} />
          )}

          {report && !loading && report.order_found !== false && (
            <>
              <div className="flex flex-wrap items-center gap-2">
                <SeverityBadge value={report.risk_level} />
                {report.order_status && <StatusBadge label={report.order_status} />}
              </div>

              {report.note && (
                <div className="rounded-md bg-[var(--ric-page-bg)] px-3 py-2.5 text-sm text-[var(--ric-text-secondary)]">
                  {report.note}
                </div>
              )}

              {/* ---- Order details ---- */}
              <section>
                <h3 className="mb-2 text-sm font-semibold text-[var(--ric-text-primary)]">Order details</h3>
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                  <div className="rounded-md border border-[var(--ric-border)] p-3">
                    <p className="text-xs text-[var(--ric-text-secondary)]">Customer</p>
                    <p className="mt-1 text-sm font-semibold text-[var(--ric-text-primary)]">
                      {report.customer_id ?? "Unknown"}
                    </p>
                  </div>
                  <div className="rounded-md border border-[var(--ric-border)] p-3">
                    <p className="text-xs text-[var(--ric-text-secondary)]">Quantity</p>
                    <p className="mt-1 text-sm font-semibold text-[var(--ric-text-primary)]">
                      {report.quantity ?? "Unknown"}
                    </p>
                  </div>
                  <div className="rounded-md border border-[var(--ric-border)] p-3">
                    <p className="text-xs text-[var(--ric-text-secondary)]">Order date</p>
                    <p className="mt-1 text-sm font-semibold text-[var(--ric-text-primary)]">
                      {report.order_date ?? "Unknown"}
                    </p>
                  </div>
                  <div className="rounded-md border border-[var(--ric-border)] p-3">
                    <p className="text-xs text-[var(--ric-text-secondary)]">Fulfillment location</p>
                    <p className="mt-1 text-sm font-semibold text-[var(--ric-text-primary)]">
                      {report.fulfillment_location ?? "Unknown"}{" "}
                      {report.fulfillment_location_type && report.fulfillment_location_type !== "unknown"
                        ? `(${report.fulfillment_location_type})`
                        : ""}
                    </p>
                  </div>
                  <div className="rounded-md border border-[var(--ric-border)] p-3 sm:col-span-2">
                    <p className="text-xs text-[var(--ric-text-secondary)]">Promised delivery date</p>
                    <p className="mt-1 text-sm font-semibold text-[var(--ric-text-primary)]">
                      {report.promised_delivery_date ?? "Not recorded"}
                    </p>
                    <p className="mt-1 text-xs text-[var(--ric-text-secondary)]">{deliveryTimingLabel(report)}</p>
                  </div>
                </div>
              </section>

              {/* ---- Delivery feasibility -- always "unknown", never invented ---- */}
              <section>
                <h3 className="mb-2 text-sm font-semibold text-[var(--ric-text-primary)]">Delivery feasibility</h3>
                <div className="rounded-md border border-[var(--ric-border)] p-3 text-sm">
                  <Badge label="Unknown -- not computable" tone="neutral" dot />
                  <p className="mt-2 text-xs text-[var(--ric-text-secondary)]">
                    {report.delivery_feasibility?.reason ??
                      "This dataset has no shipment tracking, carrier information, actual delivery dates, or outbound transit-time data."}
                  </p>
                </div>
              </section>

              {/* ---- Inventory readiness ---- */}
              <section>
                <h3 className="mb-2 text-sm font-semibold text-[var(--ric-text-primary)]">
                  Inventory readiness at fulfillment location
                </h3>
                {report.inventory_readiness ? (
                  <div className="rounded-md border border-[var(--ric-border)] p-3 text-sm">
                    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                      <div>
                        <p className="text-xs text-[var(--ric-text-secondary)]">Eligible available</p>
                        <p className="mt-0.5 font-semibold text-[var(--ric-text-primary)]">
                          {report.inventory_readiness.eligible_available_at_location ?? "Unknown"}
                        </p>
                      </div>
                      <div>
                        <p className="text-xs text-[var(--ric-text-secondary)]">Quantity required</p>
                        <p className="mt-0.5 font-semibold text-[var(--ric-text-primary)]">
                          {report.inventory_readiness.quantity_required ?? "Unknown"}
                        </p>
                      </div>
                      <div>
                        <p className="text-xs text-[var(--ric-text-secondary)]">Shortfall</p>
                        <p className="mt-0.5 font-semibold text-[var(--ric-text-primary)]">
                          {report.inventory_readiness.shortfall ?? "None"}
                        </p>
                      </div>
                    </div>
                    <div className="mt-2">
                      {report.inventory_readiness.sufficient == null ? (
                        <Badge label="Sufficiency unknown" tone="neutral" dot />
                      ) : report.inventory_readiness.sufficient ? (
                        <Badge label="Sufficient" tone="success" dot />
                      ) : (
                        <Badge label="Insufficient" tone="danger" dot />
                      )}
                    </div>
                    {report.inventory_readiness.data_limitation && (
                      <p className="mt-2 text-xs text-amber-700">{report.inventory_readiness.data_limitation}</p>
                    )}
                    <p className="mt-2 text-xs text-[var(--ric-text-secondary)]">
                      {report.inventory_readiness.provisional_reason}
                    </p>
                  </div>
                ) : (
                  <EmptyState message="Inventory readiness not available." />
                )}
              </section>

              {/* ---- Demand context ---- */}
              {report.demand_context && (
                <section>
                  <h3 className="mb-2 text-sm font-semibold text-[var(--ric-text-primary)]">
                    Demand context (estimate)
                  </h3>
                  <div className="rounded-md border border-[var(--ric-border)] p-3 text-sm text-[var(--ric-text-primary)]">
                    {report.demand_context.available ? (
                      <p>
                        Forecast demand (estimate) over the next {report.demand_context.horizon_days} day(s):{" "}
                        <strong>{report.demand_context.forecast_total_demand}</strong>
                      </p>
                    ) : (
                      <p className="text-[var(--ric-text-secondary)]">
                        Demand forecast unavailable: {report.demand_context.reason}
                      </p>
                    )}
                  </div>
                </section>
              )}

              {/* ---- Promotion context ---- */}
              {report.promotion_context?.has_relevant_promotion && (
                <section>
                  <h3 className="mb-2 text-sm font-semibold text-[var(--ric-text-primary)]">Promotion context</h3>
                  <div className="rounded-md border border-[var(--ric-border)] p-3 text-sm">
                    <ul className="list-disc space-y-1 pl-5 text-[var(--ric-text-primary)]">
                      {report.promotion_context.promotions.map((p) => (
                        <li key={p.promotion_id}>
                          {p.promotion_id} ({p.status}): {p.start_date} to {p.end_date}
                        </li>
                      ))}
                    </ul>
                    <p className="mt-2 text-xs text-[var(--ric-text-secondary)]">{report.promotion_context.note}</p>
                  </div>
                </section>
              )}

              {/* ---- Alternative fulfillment options ---- */}
              {report.alternative_fulfillment_options && (
                <section>
                  <h3 className="mb-2 text-sm font-semibold text-[var(--ric-text-primary)]">
                    Alternative fulfillment options
                  </h3>
                  {report.alternative_fulfillment_options.length === 0 ? (
                    <EmptyState message="No alternative store or warehouse locations found for this SKU." />
                  ) : (
                    <>
                      <DataTable
                        columns={alternativeColumns}
                        rows={report.alternative_fulfillment_options}
                        rowKey={(r) => r.location_id}
                        emptyMessage="No alternative fulfillment candidates."
                      />
                      <p className="mt-2 text-xs text-[var(--ric-text-secondary)]">
                        No outbound transit-time data exists between any location and the customer in this dataset
                        -- even a sufficient-stock candidate requires manual validation before any reassignment.
                        Nothing here is reassigned automatically.
                      </p>
                    </>
                  )}
                </section>
              )}

              {/* ---- Recommended next actions ---- */}
              <section>
                <h3 className="mb-2 text-sm font-semibold text-[var(--ric-text-primary)]">
                  Recommended next actions
                </h3>
                {report.recommendations.length === 0 ? (
                  <EmptyState message="No elevated risk signals for this order right now -- no action needed." />
                ) : (
                  <ul className="list-disc space-y-1 pl-5 text-sm text-[var(--ric-text-primary)]">
                    {report.recommendations.map((rec, i) => (
                      <li key={i}>{rec}</li>
                    ))}
                  </ul>
                )}
                <p className="mt-2 text-xs text-[var(--ric-text-secondary)]">
                  {report.disclaimer ??
                    "All recommendations are read-only and require human approval. This agent never changes an order status, reassigns a fulfillment location, transfers stock, cancels an order, issues a refund, or sends any customer communication."}
                </p>
              </section>

              {report.data_quality_warning && <DataGapsPanel gaps={[report.data_quality_warning]} />}

              <EvidencePanel evidence={report} />
            </>
          )}
        </div>
      </div>
    </div>
  );
}
