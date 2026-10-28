"use client";

/**
 * Per-SKU promotion detail: full promotion history with historical
 * before/after comparisons, plus a readiness assessment for each
 * upcoming/active promotion. Everything comes from one call --
 * GET /promotions/{sku} (PromotionIntelligenceEngine.analyze_promotion_for_sku)
 * -- no recomputation here.
 *
 * Two kinds of numbers appear in this component and they are never
 * blended or relabeled into each other:
 *  - "Historical observation" (historical_comparison): a measured sales
 *    difference between an actual past promo window and its preceding
 *    baseline window. comparable=false (with a reason) when the data
 *    can't support one -- shown as such, never as a zero or a guess.
 *  - "Estimated promotional demand" (promotional_demand_estimate): the
 *    Demand Forecasting Agent's baseline forecast, optionally adjusted by
 *    an uplift percentage that is EITHER a real historical observation for
 *    this exact SKU (source="historical_uplift") OR an explicit what-if
 *    assumption (source="assumed_scenario") OR left unknown. Neither case
 *    is presented as proof the promotion caused a sales change -- the
 *    uplift disclaimer text from the backend is shown verbatim wherever an
 *    observed percent change appears.
 */

import { useEffect, useRef, useState } from "react";
import { X } from "lucide-react";

import { ApiError, getPromotionAnalysisForSku } from "@/lib/api";
import type { PromotionHistoryEntry, PromotionReadinessItem, SkuPromotionAnalysis } from "@/lib/types";
import { Badge, type BadgeTone } from "@/components/ui/Badge";
import { DataTable, type DataTableColumn } from "@/components/ui/DataTable";
import { DataGapsPanel } from "@/components/retail/DataGapsPanel";
import { EmptyState } from "@/components/retail/EmptyState";
import { ErrorState } from "@/components/retail/ErrorState";
import { EvidencePanel } from "@/components/retail/EvidencePanel";
import { LoadingState } from "@/components/retail/LoadingState";
import { SeverityBadge } from "@/components/retail/SeverityBadge";
import { StatusBadge } from "@/components/retail/StatusBadge";

const UPLIFT_SOURCE_LABELS: Record<string, { label: string; tone: BadgeTone }> = {
  historical_uplift: { label: "Historical uplift (observed)", tone: "info" },
  assumed_scenario: { label: "Assumed scenario (what-if)", tone: "warning" },
  unknown: { label: "Unknown -- baseline only", tone: "neutral" },
};

function promotionLabel(promo: PromotionHistoryEntry | undefined, promotionId: string): string {
  return promo ? `${promo.promotion_name} (${promotionId})` : `Promotion ${promotionId}`;
}

export function PromotionDetailDrawer({ sku, onClose }: { sku: string; onClose: () => void }) {
  const [analysis, setAnalysis] = useState<SkuPromotionAnalysis | null>(null);
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

    getPromotionAnalysisForSku(sku)
      .then((a) => {
        if (cancelled) return;
        setAnalysis(a);
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
  }, [sku]);

  useEffect(() => {
    panelRef.current?.focus();
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  const promotionColumns: DataTableColumn<PromotionHistoryEntry>[] = [
    { key: "name", header: "Promotion", sortable: true, accessor: (r) => r.promotion_name },
    { key: "discount", header: "Discount", align: "right", accessor: (r) => `${r.discount_percent}%` },
    { key: "channel", header: "Channel", accessor: (r) => r.promotion_channel },
    { key: "dates", header: "Dates", accessor: (r) => `${r.start_date} to ${r.end_date}` },
    { key: "status", header: "Status", accessor: (r) => r.status, render: (r) => <StatusBadge label={r.status} /> },
    {
      key: "overlap",
      header: "Overlap",
      align: "center",
      accessor: (r) => (r.overlaps_another_promotion_for_this_sku ? "Yes" : "No"),
      render: (r) =>
        r.overlaps_another_promotion_for_this_sku ? (
          <Badge label="Overlaps another promo" tone="warning" />
        ) : (
          "No"
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
        aria-labelledby="promotion-detail-title"
        tabIndex={-1}
        className="relative z-50 flex h-full w-full max-w-2xl flex-col overflow-y-auto bg-[var(--ric-card-bg)] shadow-lg outline-none"
      >
        <div className="flex items-start justify-between gap-3 border-b border-[var(--ric-border)] px-5 py-4">
          <div>
            <h2 id="promotion-detail-title" className="text-sm font-semibold text-[var(--ric-text-primary)]">
              {sku} {analysis?.product_name ? `-- ${analysis.product_name}` : ""}
            </h2>
            <p className="mt-0.5 text-xs text-[var(--ric-text-secondary)]">Promotion history &amp; readiness</p>
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
          {loading && <LoadingState message="Loading promotion detail..." />}
          {error && <ErrorState message={error} />}

          {analysis && !loading && !analysis.has_promotion_history && (
            <EmptyState message={analysis.note ?? "No promotion history found for this SKU."} />
          )}

          {analysis && !loading && analysis.has_promotion_history && (
            <>
              <section>
                <h3 className="mb-2 text-sm font-semibold text-[var(--ric-text-primary)]">
                  Promotion history for this SKU
                </h3>
                <DataTable
                  columns={promotionColumns}
                  rows={analysis.promotions}
                  rowKey={(r) => r.promotion_id}
                  emptyMessage="No promotions recorded."
                />
              </section>

              <section>
                <h3 className="mb-2 text-sm font-semibold text-[var(--ric-text-primary)]">
                  Historical observations (measured, not promotional-uplift estimates)
                </h3>
                <p className="mb-2 text-xs text-[var(--ric-text-secondary)]">
                  Each comparison below measures actual sales during a past promotional window against the
                  immediately preceding, same-length baseline window. This does not prove the promotion caused any
                  difference -- other factors (seasonality, other concurrent events, random variation) may also
                  contribute.
                </p>
                <ul className="space-y-2">
                  {analysis.promotions.map((promo) => {
                    const c = promo.historical_comparison;
                    return (
                      <li
                        key={promo.promotion_id}
                        className="rounded-lg border border-[var(--ric-border)] p-3 text-sm"
                      >
                        <p className="font-medium text-[var(--ric-text-primary)]">{promo.promotion_name}</p>
                        {c.comparable ? (
                          <p className="mt-1 text-[var(--ric-text-primary)]">
                            Observed avg daily units: <strong>{c.observed_avg_daily_units_during_promotion}</strong>{" "}
                            during the promotion ({c.promo_period.start} to {c.promo_period.end}) vs.{" "}
                            <strong>{c.observed_avg_daily_units_baseline}</strong> in the preceding baseline window
                            ({c.baseline_period.start} to {c.baseline_period.end}) -- a{" "}
                            <strong>
                              {c.observed_percent_change != null && c.observed_percent_change > 0 ? "+" : ""}
                              {c.observed_percent_change}%
                            </strong>{" "}
                            observed difference.
                          </p>
                        ) : (
                          <p className="mt-1 text-[var(--ric-text-secondary)]">
                            Not comparable: {c.reason ?? "insufficient data"}.
                          </p>
                        )}
                        {c.disclaimer && <p className="mt-1 text-xs text-[var(--ric-text-secondary)]">{c.disclaimer}</p>}
                      </li>
                    );
                  })}
                </ul>
              </section>

              <section>
                <h3 className="mb-2 text-sm font-semibold text-[var(--ric-text-primary)]">
                  Readiness assessment (upcoming/active promotions)
                </h3>
                {analysis.readiness_reports.length === 0 ? (
                  <EmptyState message="No upcoming or active promotions for this SKU right now." />
                ) : (
                  <div className="space-y-4">
                    {analysis.readiness_reports.map((r) => (
                      <ReadinessReportCard
                        key={r.promotion_id}
                        report={r}
                        promo={analysis.promotions.find((p) => p.promotion_id === r.promotion_id)}
                      />
                    ))}
                  </div>
                )}
              </section>

              {analysis.data_quality_warnings && <DataGapsPanel gaps={analysis.data_quality_warnings} />}

              <EvidencePanel evidence={analysis} />
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function ReadinessReportCard({
  report,
  promo,
}: {
  report: PromotionReadinessItem;
  promo: PromotionHistoryEntry | undefined;
}) {
  const uplift = UPLIFT_SOURCE_LABELS[report.promotional_demand_estimate.source] ?? UPLIFT_SOURCE_LABELS.unknown;

  return (
    <div className="rounded-lg border border-[var(--ric-border)] p-3 text-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="font-medium text-[var(--ric-text-primary)]">{promotionLabel(promo, report.promotion_id)}</p>
        <SeverityBadge value={report.readiness_status} />
      </div>
      <p className="mt-1 text-xs text-[var(--ric-text-secondary)]">
        {report.start_date} to {report.end_date} -- {report.days_until_start} day(s) until start
        {report.inventory_agent_risk_level ? ` -- inventory risk: ` : ""}
        {report.inventory_agent_risk_level && <SeverityBadge value={report.inventory_agent_risk_level} />}
      </p>

      <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3">
        <div className="rounded-lg bg-[var(--ric-page-bg)] p-2.5">
          <p className="text-xs text-[var(--ric-text-secondary)]">Baseline demand (estimate)</p>
          <p className="mt-0.5 text-base font-semibold text-[var(--ric-text-primary)]">
            {report.baseline_forecast_demand ?? "Unavailable"}
          </p>
        </div>
        <div className="rounded-lg bg-[var(--ric-page-bg)] p-2.5">
          <p className="text-xs text-[var(--ric-text-secondary)]">Current inventory</p>
          <p className="mt-0.5 text-base font-semibold text-[var(--ric-text-primary)]">
            {report.observed?.current_available_inventory ?? "Unavailable"}
          </p>
        </div>
        <div className="rounded-lg bg-[var(--ric-page-bg)] p-2.5">
          <p className="text-xs text-[var(--ric-text-secondary)]">Eligible warehouse stock</p>
          <p className="mt-0.5 text-base font-semibold text-[var(--ric-text-primary)]">
            {report.observed?.warehouse_available_stock ?? "Unavailable"}
          </p>
        </div>
        <div className="rounded-lg bg-[var(--ric-page-bg)] p-2.5">
          <p className="text-xs text-[var(--ric-text-secondary)]">Eligible inbound (within promo)</p>
          <p className="mt-0.5 text-base font-semibold text-[var(--ric-text-primary)]">
            {report.observed?.known_inbound_stock_eligible_within_promotion ?? "Unavailable"}
          </p>
        </div>
        <div className="rounded-lg bg-[var(--ric-page-bg)] p-2.5">
          <p className="text-xs text-[var(--ric-text-secondary)]">Max known supplier lead time</p>
          <p className="mt-0.5 text-base font-semibold text-[var(--ric-text-primary)]">
            {report.observed?.max_known_supplier_lead_time_days ?? "Unknown"}{" "}
            {report.observed?.max_known_supplier_lead_time_days != null ? "day(s)" : ""}
          </p>
        </div>
        <div className="rounded-lg bg-[var(--ric-page-bg)] p-2.5">
          <p className="text-xs text-[var(--ric-text-secondary)]">Demand gap</p>
          <p className="mt-0.5 text-base font-semibold text-[var(--ric-text-primary)]">
            {report.demand_gap ?? "Unavailable"}
          </p>
        </div>
      </div>

      <div className="mt-3 rounded-lg bg-[var(--ric-page-bg)] p-2.5">
        <div className="flex flex-wrap items-center gap-2">
          <p className="text-xs text-[var(--ric-text-secondary)]">Estimated promotional demand:</p>
          <Badge label={uplift.label} tone={uplift.tone} dot />
        </div>
        <p className="mt-1 text-base font-semibold text-[var(--ric-text-primary)]">
          {report.promotional_demand_estimate.estimated_total_demand ?? "Not estimated -- baseline forecast used"}
        </p>
        {report.promotional_demand_estimate.uplift_pct_used != null && (
          <p className="mt-0.5 text-xs text-[var(--ric-text-secondary)]">
            Uplift applied: {report.promotional_demand_estimate.uplift_pct_used}% (
            {report.promotional_demand_estimate.source === "historical_uplift"
              ? "from this SKU's own comparable historical promotion above"
              : "from an assumed scenario, not a measurement"}
            ). This is an estimate, not a guarantee.
          </p>
        )}
      </div>

      {report.recommendations && report.recommendations.length > 0 && (
        <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-[var(--ric-text-primary)]">
          {report.recommendations.map((rec, i) => (
            <li key={i}>{rec}</li>
          ))}
        </ul>
      )}

      {report.data_quality_warnings && <DataGapsPanel gaps={report.data_quality_warnings} />}

      {report.disclaimer && <p className="mt-2 text-xs text-[var(--ric-text-secondary)]">{report.disclaimer}</p>}
    </div>
  );
}
