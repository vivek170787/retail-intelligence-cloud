"use client";

/**
 * Order-level customer-experience drill-down. Everything comes from one
 * call -- GET /customer-experience/orders/{order_id}
 * (CustomerExperienceEngine.analyze_customer_order_experience) -- which
 * itself reuses OrderFulfillmentEngine.analyze_order_fulfillment() for
 * every fulfillment/inventory fact; no new computation happens here.
 *
 * customer_id is always a synthetic CUST-NNNNN identifier -- this dataset
 * has no name, email, phone, or address field anywhere, and this
 * component never fabricates or looks up any of those.
 *
 * This component is careful never to:
 *  - claim a specific recovery action (discount, expedite, etc.) -- there
 *    is no policy dataset, so only "human review may be warranted" is
 *    ever shown, never a concrete action;
 *  - recommend a specific alternative product -- there is no
 *    substitutability mapping in this dataset;
 *  - imply any message, cancellation, refund, or inventory transfer
 *    happens automatically -- the disclaimer is always shown verbatim.
 */

import { useEffect, useRef, useState } from "react";
import { X } from "lucide-react";

import { ApiError, getCustomerOrderExperience } from "@/lib/api";
import type { CustomerImpactRiskItem } from "@/lib/types";
import { Badge, type BadgeTone } from "@/components/ui/Badge";
import { DataGapsPanel } from "@/components/retail/DataGapsPanel";
import { EmptyState } from "@/components/retail/EmptyState";
import { ErrorState } from "@/components/retail/ErrorState";
import { EvidencePanel } from "@/components/retail/EvidencePanel";
import { LoadingState } from "@/components/retail/LoadingState";
import { SeverityBadge } from "@/components/retail/SeverityBadge";
import { StatusBadge } from "@/components/retail/StatusBadge";

const PROBLEM_TYPE_LABELS: Record<string, { label: string; tone: BadgeTone }> = {
  confirmed: { label: "Confirmed problem", tone: "danger" },
  predicted: { label: "Predicted risk", tone: "warning" },
  unknown: { label: "Unknown -- insufficient data", tone: "neutral" },
  none: { label: "No risk identified", tone: "success" },
  not_applicable: { label: "Not applicable", tone: "neutral" },
};

export function CustomerExperienceDetailDrawer({ orderId, onClose }: { orderId: string; onClose: () => void }) {
  const [report, setReport] = useState<CustomerImpactRiskItem | null>(null);
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

    getCustomerOrderExperience(orderId)
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

  const problemType = report?.problem_type ? PROBLEM_TYPE_LABELS[report.problem_type] : undefined;

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-black/30" onClick={onClose} aria-hidden="true" />
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="cx-detail-title"
        tabIndex={-1}
        className="relative z-50 flex h-full w-full max-w-2xl flex-col overflow-y-auto bg-[var(--ric-card-bg)] shadow-lg outline-none"
      >
        <div className="flex items-start justify-between gap-3 border-b border-[var(--ric-border)] px-5 py-4">
          <div>
            <h2 id="cx-detail-title" className="text-sm font-semibold text-[var(--ric-text-primary)]">
              {orderId} {report?.sku ? `-- ${report.sku}` : ""}
            </h2>
            <p className="mt-0.5 text-xs text-[var(--ric-text-secondary)]">Customer experience detail</p>
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
          {loading && <LoadingState message="Loading customer experience detail..." />}
          {error && <ErrorState message={error} />}

          {report && !loading && report.order_found === false && (
            <EmptyState message={report.note ?? `No order found with order_id ${orderId}.`} />
          )}

          {report && !loading && report.order_found !== false && (
            <>
              <div className="flex flex-wrap items-center gap-2">
                <SeverityBadge value={report.severity} />
                {problemType && <Badge label={problemType.label} tone={problemType.tone} dot />}
                {report.order_status && <StatusBadge label={report.order_status} />}
              </div>

              <p className="text-xs text-[var(--ric-text-secondary)]">
                Customer (synthetic ID): <span className="font-medium">{report.customer_id ?? "Unknown"}</span> --
                this dataset has no name, email, phone, or address field; nothing beyond this synthetic identifier
                is shown or stored here.
              </p>

              {/* ---- Problem assessment ---- */}
              <section>
                <h3 className="mb-2 text-sm font-semibold text-[var(--ric-text-primary)]">Problem assessment</h3>
                <div className="rounded-md border border-[var(--ric-border)] p-3 text-sm text-[var(--ric-text-primary)]">
                  {report.explanation ?? "No explanation available."}
                </div>
                {report.missing_information && report.missing_information.length > 0 && (
                  <div className="mt-2">
                    <DataGapsPanel gaps={report.missing_information} />
                  </div>
                )}
              </section>

              {/* ---- Supporting evidence ---- */}
              {report.fulfillment_assessment && (
                <section>
                  <h3 className="mb-2 text-sm font-semibold text-[var(--ric-text-primary)]">Supporting evidence</h3>
                  <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                    <div className="rounded-md border border-[var(--ric-border)] p-3">
                      <p className="text-xs text-[var(--ric-text-secondary)]">Fulfillment location</p>
                      <p className="mt-1 text-sm font-semibold text-[var(--ric-text-primary)]">
                        {report.fulfillment_location ?? "Unknown"}
                      </p>
                    </div>
                    <div className="rounded-md border border-[var(--ric-border)] p-3">
                      <p className="text-xs text-[var(--ric-text-secondary)]">Promised delivery date</p>
                      <p className="mt-1 text-sm font-semibold text-[var(--ric-text-primary)]">
                        {report.fulfillment_assessment.promised_delivery_date ?? "Not recorded"}
                      </p>
                    </div>
                    <div className="rounded-md border border-[var(--ric-border)] p-3">
                      <p className="text-xs text-[var(--ric-text-secondary)]">Inventory at location sufficient?</p>
                      <p className="mt-1 text-sm font-semibold text-[var(--ric-text-primary)]">
                        {report.fulfillment_assessment.inventory_readiness?.sufficient == null
                          ? "Unknown"
                          : report.fulfillment_assessment.inventory_readiness.sufficient
                            ? "Yes"
                            : `No (short ${report.fulfillment_assessment.inventory_readiness.shortfall ?? "?"})`}
                      </p>
                    </div>
                  </div>
                  <p className="mt-2 text-xs text-[var(--ric-text-secondary)]">
                    Delivery feasibility: <strong>unknown</strong> -- this dataset has no shipment tracking, carrier
                    information, actual delivery dates, or outbound transit-time data. No delivery date is promised
                    or estimated here beyond the order&apos;s own recorded promised_delivery_date.
                  </p>
                </section>
              )}

              {/* ---- Inventory-related / availability risk ---- */}
              <section>
                <h3 className="mb-2 text-sm font-semibold text-[var(--ric-text-primary)]">
                  Marketplace availability context
                </h3>
                {report.marketplace_context ? (
                  report.marketplace_context.has_marketplace_listings ? (
                    <div className="rounded-md border border-[var(--ric-border)] p-3 text-sm">
                      {report.marketplace_context.any_availability_issue ? (
                        <>
                          <Badge label="Availability issue flagged" tone="warning" dot />
                          <p className="mt-2 text-[var(--ric-text-primary)]">
                            Affected marketplace(s): {report.marketplace_context.affected_marketplaces?.join(", ")}
                          </p>
                        </>
                      ) : (
                        <Badge label="No marketplace availability issues" tone="success" dot />
                      )}
                      {report.marketplace_context.note && (
                        <p className="mt-2 text-xs text-[var(--ric-text-secondary)]">{report.marketplace_context.note}</p>
                      )}
                    </div>
                  ) : (
                    <EmptyState message="This SKU has no marketplace listings." />
                  )
                ) : (
                  <EmptyState message="Marketplace context unavailable." />
                )}
              </section>

              {/* ---- Potential cancellation risk ---- */}
              <section>
                <h3 className="mb-2 text-sm font-semibold text-[var(--ric-text-primary)]">
                  Potential cancellation risk
                </h3>
                <div className="rounded-md border border-[var(--ric-border)] p-3 text-sm">
                  {report.potential_cancellation_risk?.flagged ? (
                    <>
                      <Badge label="Flagged for human review" tone="danger" dot />
                      <p className="mt-2 text-[var(--ric-text-primary)]">{report.potential_cancellation_risk.reason}</p>
                    </>
                  ) : (
                    <Badge label="Not flagged" tone="neutral" dot />
                  )}
                </div>
              </section>

              {/* ---- Alternative product ---- */}
              <section>
                <h3 className="mb-2 text-sm font-semibold text-[var(--ric-text-primary)]">
                  Alternative product recommendation
                </h3>
                <EmptyState
                  message={
                    report.alternative_product_recommendation?.reason ??
                    "Not available -- no product substitutability data exists in this dataset."
                  }
                />
              </section>

              {/* ---- Human-reviewed recovery action ---- */}
              <section>
                <h3 className="mb-2 text-sm font-semibold text-[var(--ric-text-primary)]">
                  Service recovery action
                </h3>
                <div className="rounded-md border border-[var(--ric-border)] p-3 text-sm">
                  {report.human_reviewed_recovery_action?.suggested ? (
                    <Badge label="Human review may be warranted" tone="warning" dot />
                  ) : (
                    <Badge label="No human review flagged" tone="neutral" dot />
                  )}
                  <p className="mt-2 text-xs text-[var(--ric-text-secondary)]">
                    {report.human_reviewed_recovery_action?.reason}
                  </p>
                  <p className="mt-1 text-xs font-medium text-[var(--ric-text-secondary)]">
                    No specific action (discount, expedite, refund, cancellation, or message) is recommended or
                    taken automatically.
                  </p>
                </div>
              </section>

              {/* ---- Recommended next actions ---- */}
              <section>
                <h3 className="mb-2 text-sm font-semibold text-[var(--ric-text-primary)]">
                  Recommended next actions
                </h3>
                {report.recommended_actions.length === 0 ? (
                  <EmptyState message="No elevated risk signals for this order right now -- no action needed." />
                ) : (
                  <ul className="list-disc space-y-1 pl-5 text-sm text-[var(--ric-text-primary)]">
                    {report.recommended_actions.map((rec, i) => (
                      <li key={i}>{rec}</li>
                    ))}
                  </ul>
                )}
                <p className="mt-2 text-xs text-[var(--ric-text-secondary)]">
                  {report.disclaimer ??
                    "All recommendations are read-only and require human approval. This agent never changes an order, cancels or refunds anything, transfers inventory, or sends any customer communication or external API call."}
                </p>
              </section>

              <EvidencePanel evidence={report} />
            </>
          )}
        </div>
      </div>
    </div>
  );
}
