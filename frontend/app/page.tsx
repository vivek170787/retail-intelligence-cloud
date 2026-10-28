"use client";

/**
 * Retail Command Center (Executive Overview workspace) -- every KPI,
 * chart, and table on this page is sourced from a real existing API
 * route; nothing is invented. Where a requested field genuinely doesn't
 * exist anywhere in the backend (a dollar "expected business impact",
 * a numeric confidence score), the cell says so explicitly ("Not
 * estimated") rather than showing a plausible-looking fabricated number --
 * see the Recommended Actions section below.
 */

import { useMemo, useState } from "react";
import {
  Heart,
  MapPin,
  Package,
  RefreshCw,
  ShoppingCart,
  Tag,
  TrendingDown,
  TrendingUp,
  Truck,
} from "lucide-react";

import {
  getCustomerImpactRisks,
  getDashboardSummary,
  getFulfillmentPriorities,
  getInventoryReplenishment,
  getPromotionReadiness,
  getSalesTrend,
  getServiceRecoveryRecommendations,
  getTopStockoutRisks,
} from "@/lib/api";
import { useApi } from "@/lib/useApi";
import { SEVERITY_DISPLAY_ORDER } from "@/lib/severity";
import type { InventoryRiskItem } from "@/lib/types";
import { Badge } from "@/components/ui/Badge";
import { DataTable, type DataTableColumn } from "@/components/ui/DataTable";
import { SelectFilter } from "@/components/ui/SelectFilter";
import { Card, CardBody, CardHeader } from "@/components/retail/Card";
import { DataFreshnessNote } from "@/components/retail/DataFreshnessNote";
import { DataGapsPanel } from "@/components/retail/DataGapsPanel";
import { DisclaimerFooter } from "@/components/retail/DisclaimerFooter";
import { EmptyState } from "@/components/retail/EmptyState";
import { ErrorState } from "@/components/retail/ErrorState";
import { KpiCard } from "@/components/retail/KpiCard";
import { LoadingState } from "@/components/retail/LoadingState";
import { ReviewActionButton } from "@/components/retail/ReviewActionButton";
import { RiskBreakdownChart } from "@/components/retail/RiskBreakdownChart";
import { SeverityBadge } from "@/components/retail/SeverityBadge";
import { TrendLineChart } from "@/components/retail/TrendLineChart";

const PROMOTION_HORIZON_OPTIONS = [
  { value: "7", label: "Next 7 days" },
  { value: "14", label: "Next 14 days" },
  { value: "30", label: "Next 30 days" },
];

const REPORTING_PERIOD_OPTIONS = [
  { value: "7", label: "Last 7 days" },
  { value: "30", label: "Last 30 days" },
  { value: "90", label: "Last 90 days" },
];

const INVENTORY_BASIS_LABELS: Record<string, string> = {
  target_days_of_coverage: "Based on recent sales velocity (target days of coverage)",
  no_recent_sales_velocity: "Low confidence -- no recent sales velocity data",
};

const PROMO_SOURCE_LABELS: Record<string, string> = {
  historical_uplift: "Higher confidence -- based on this SKU's historical promo uplift",
  assumed_scenario: "Lower confidence -- based on an assumed uplift scenario, not historical data",
  unknown: "Confidence unknown -- insufficient data to estimate uplift",
};

const NOT_ESTIMATED = "Not estimated";

interface ActionRow {
  id: string;
  issue: string;
  affected: string;
  severityValue: string;
  evidence: string;
  action: string;
  impact: string;
  confidence: string;
}

function severityRank(value: string): number {
  const idx = SEVERITY_DISPLAY_ORDER.indexOf(value);
  return idx === -1 ? SEVERITY_DISPLAY_ORDER.length : idx;
}

export default function ExecutiveOverviewPage() {
  const [promotionHorizonDays, setPromotionHorizonDays] = useState(7);
  const [reportingPeriodDays, setReportingPeriodDays] = useState(30);

  const summary = useApi(() => getDashboardSummary(promotionHorizonDays), [promotionHorizonDays]);
  const trend = useApi(() => getSalesTrend(), []);
  const topStockoutRisks = useApi(() => getTopStockoutRisks(10), []);
  const replenishment = useApi(() => getInventoryReplenishment(), []);
  const promotionReadiness = useApi(() => getPromotionReadiness(), []);
  const fulfillmentPriorities = useApi(() => getFulfillmentPriorities(20), []);
  const serviceRecovery = useApi(() => getServiceRecoveryRecommendations(), []);
  const customerImpactRisks = useApi(() => getCustomerImpactRisks(), []);

  const data = summary.data;

  const trendPoints = useMemo(() => {
    if (!trend.data || trend.data.dates.length === 0) return [];
    const sliceFrom = Math.max(0, trend.data.dates.length - reportingPeriodDays);
    return trend.data.dates.slice(sliceFrom).map((date, i) => ({
      date,
      value: trend.data!.values[sliceFrom + i],
    }));
  }, [trend.data, reportingPeriodDays]);

  const actualLast7Days = useMemo(() => {
    if (!trend.data || trend.data.values.length === 0) return null;
    return trend.data.values.slice(-7).reduce((sum, v) => sum + v, 0);
  }, [trend.data]);

  const forecastedDemandNext7d = useMemo(() => {
    const raw = data?.demand_summary?.total_forecast_demand_next_horizon;
    return typeof raw === "number" ? Math.round(raw) : null;
  }, [data]);

  const cxSeverityCounts = useMemo(() => {
    if (!customerImpactRisks.data) return null;
    const counts: Record<string, number> = {};
    for (const risk of customerImpactRisks.data) {
      counts[risk.severity] = (counts[risk.severity] ?? 0) + 1;
    }
    return counts;
  }, [customerImpactRisks.data]);

  const actionRows: ActionRow[] = useMemo(() => {
    const rows: ActionRow[] = [];

    if (replenishment.data) {
      for (const item of replenishment.data as InventoryRiskItem[]) {
        rows.push({
          id: `inv-${item.sku}`,
          issue: "Inventory stockout risk",
          affected: item.product?.product_name ? `${item.sku} -- ${item.product.product_name}` : item.sku,
          severityValue: item.estimated.risk_level,
          evidence: `${item.estimated.days_of_inventory ?? "Unknown"} day(s) of inventory remaining at ~${item.estimated.avg_daily_sales_7d}/day (7d avg)`,
          action: `Investigate replenishment -- suggested quantity: ${item.recommendation.suggested_replenishment_quantity}`,
          impact: NOT_ESTIMATED,
          confidence: INVENTORY_BASIS_LABELS[item.recommendation.basis] ?? item.recommendation.basis,
        });
      }
    }

    if (promotionReadiness.data) {
      for (const r of promotionReadiness.data.reports) {
        if (r.readiness_status === "sufficient") continue;
        rows.push({
          id: `promo-${r.promotion_id}-${r.sku}`,
          issue: "Promotion inventory readiness",
          affected: `${r.sku} (promo ${r.promotion_id})`,
          severityValue: r.readiness_status,
          evidence: `Demand gap: ${r.demand_gap ?? "unknown"}, baseline forecast: ${r.baseline_forecast_demand ?? "unknown"}`,
          action: "Investigate replenishment before the promotion starts.",
          impact: NOT_ESTIMATED,
          confidence: PROMO_SOURCE_LABELS[r.promotional_demand_estimate?.source ?? "unknown"] ?? "Unknown",
        });
      }
    }

    if (fulfillmentPriorities.data) {
      for (const o of fulfillmentPriorities.data) {
        rows.push({
          id: `ful-${o.order_id}`,
          issue: "Order fulfillment risk",
          affected: `${o.order_id} (${o.sku})`,
          severityValue: o.risk_level,
          evidence:
            o.days_overdue != null
              ? `${o.days_overdue} day(s) overdue`
              : o.days_until_due != null
                ? `${o.days_until_due} day(s) until due`
                : "Timing unknown",
          action: o.recommendations[0] ?? "Review manually -- insufficient data to assess automatically.",
          impact: NOT_ESTIMATED,
          confidence: "Deterministic rule: promised date vs. today + inventory check",
        });
      }
    }

    if (serviceRecovery.data) {
      for (const o of serviceRecovery.data.orders) {
        rows.push({
          id: `cx-${o.order_id}`,
          issue: "Customer experience impact",
          affected: o.sku ? `${o.order_id} (${o.sku})` : o.order_id,
          severityValue: o.severity,
          evidence: "Derived from order fulfillment status and marketplace availability context.",
          action: o.recommended_actions.join("; "),
          impact: NOT_ESTIMATED,
          confidence: "Deterministic rule: fulfillment status + marketplace availability context",
        });
      }
    }

    return rows.sort((a, b) => severityRank(a.severityValue) - severityRank(b.severityValue));
  }, [replenishment.data, promotionReadiness.data, fulfillmentPriorities.data, serviceRecovery.data]);

  const VISIBLE_ACTION_LIMIT = 30;
  const visibleActionRows = actionRows.slice(0, VISIBLE_ACTION_LIMIT);

  const actionColumns: DataTableColumn<ActionRow>[] = [
    { key: "issue", header: "Issue", accessor: (r) => r.issue },
    { key: "affected", header: "Affected", accessor: (r) => r.affected },
    {
      key: "severity",
      header: "Severity",
      sortable: true,
      accessor: (r) => r.severityValue,
      render: (r) => <SeverityBadge value={r.severityValue} />,
    },
    { key: "evidence", header: "Evidence", accessor: (r) => r.evidence },
    { key: "action", header: "Recommended Action", accessor: (r) => r.action },
    { key: "impact", header: "Expected Impact", accessor: (r) => r.impact },
    { key: "confidence", header: "Confidence", accessor: (r) => r.confidence },
    {
      key: "approval",
      header: "Approval",
      accessor: () => "Human approval required",
      render: () => <Badge label="Human approval required" tone="warning" />,
    },
    {
      key: "review",
      header: "Review",
      accessor: () => "",
      render: (r) => <ReviewActionButton itemLabel={`${r.issue} -- ${r.affected}`} />,
    },
  ];

  const stockoutColumns: DataTableColumn<InventoryRiskItem>[] = [
    { key: "sku", header: "SKU", accessor: (r) => r.sku },
    { key: "product", header: "Product", accessor: (r) => r.product?.product_name ?? "Unknown" },
    {
      key: "risk",
      header: "Risk Level",
      sortable: true,
      accessor: (r) => r.estimated.risk_level,
      render: (r) => <SeverityBadge value={r.estimated.risk_level} />,
    },
    {
      key: "days",
      header: "Days of Inventory",
      align: "right",
      sortable: true,
      accessor: (r) => r.estimated.days_of_inventory ?? Number.POSITIVE_INFINITY,
      render: (r) => r.estimated.days_of_inventory ?? "Unknown",
    },
  ];

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      {/* ---- Header (subtle hero treatment -- this app has no separate marketing
           landing page, so the dashboard's own header is the closest equivalent) ---- */}
      <div className="flex flex-wrap items-start justify-between gap-4 rounded-xl border border-[var(--ric-border)] bg-gradient-to-br from-[var(--ric-pale-highlight)] to-[var(--ric-card-bg)] p-6">
        <div>
          <h1 className="text-xl font-semibold text-[var(--ric-text-primary)]">Retail Command Center</h1>
          <p className="mt-1 text-sm text-[var(--ric-text-secondary)]">
            Executive view across inventory, demand, promotions, fulfillment, and customer experience.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <SelectFilter
            label="Reporting period"
            value={String(reportingPeriodDays)}
            options={REPORTING_PERIOD_OPTIONS}
            onChange={(value) => setReportingPeriodDays(Number(value))}
          />
          <SelectFilter
            label="Promotion lookahead"
            value={String(promotionHorizonDays)}
            options={PROMOTION_HORIZON_OPTIONS}
            onChange={(value) => setPromotionHorizonDays(Number(value))}
          />
          <button
            type="button"
            disabled
            title="Store-level filtering isn't available for this catalog-wide view yet; see the per-SKU/store breakdown once the Inventory Intelligence workspace is wired up."
            className="flex items-center gap-1.5 rounded-lg border border-[var(--ric-border)] px-3 py-1.5 text-sm text-[var(--ric-text-secondary)] disabled:cursor-not-allowed"
          >
            <MapPin className="h-3.5 w-3.5" aria-hidden="true" />
            <span>All stores</span>
          </button>
          <button
            type="button"
            onClick={() => {
              summary.refetch();
              trend.refetch();
              topStockoutRisks.refetch();
              replenishment.refetch();
              promotionReadiness.refetch();
              fulfillmentPriorities.refetch();
              serviceRecovery.refetch();
              customerImpactRisks.refetch();
            }}
            className="flex items-center gap-1.5 rounded-lg border border-[var(--ric-border)] bg-[var(--ric-card-bg)] px-3 py-1.5 text-sm font-medium text-[var(--ric-text-primary)] hover:bg-[var(--ric-page-bg)]"
          >
            <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
            Refresh data
          </button>
        </div>
      </div>

      {summary.loading && <LoadingState message="Loading executive summary..." />}
      {summary.error && <ErrorState message={summary.error} />}

      {data && (
        <>
          <DataFreshnessNote note={data.dataset_note} />

          <div className="flex items-center gap-3">
            <span className="text-sm font-medium text-[var(--ric-text-secondary)]">Overall severity:</span>
            <SeverityBadge value={data.severity} />
          </div>

          <DataGapsPanel gaps={data.data_gaps} />

          {/* ---- KPI cards ---- */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <KpiCard
              label="Total Active (Open) Orders"
              value={data.fulfillment_summary?.total_open_orders ?? "Unavailable"}
              icon={ShoppingCart}
            />
            <KpiCard
              label="Inventory Stockout Risks (critical+high)"
              value={
                data.inventory_summary
                  ? (data.inventory_summary.risk_level_counts.critical ?? 0) +
                    (data.inventory_summary.risk_level_counts.high ?? 0)
                  : "Unavailable"
              }
              icon={Package}
            />
            <KpiCard
              label="Products with Excess Inventory"
              value={data.inventory_summary?.products_with_excess_inventory ?? "Unavailable"}
              icon={Package}
            />
            <KpiCard
              label="Forecasted Demand (next 7d, estimate)"
              value={forecastedDemandNext7d ?? "Unavailable"}
              icon={TrendingUp}
            />
            <KpiCard
              label="Customer-Impacting Issues"
              value={data.cx_summary?.total_customer_impact_risks ?? "Unavailable"}
              icon={Heart}
            />
            <KpiCard
              label="Orders at Risk of Late Delivery"
              value={
                data.fulfillment_summary
                  ? (data.fulfillment_summary.risk_counts.critical ?? 0) +
                    (data.fulfillment_summary.risk_counts.high ?? 0)
                  : "Unavailable"
              }
              icon={Truck}
            />
            <KpiCard
              label={`Upcoming Promotions (next ${promotionHorizonDays}d)`}
              value={data.upcoming_promotions_count ?? "Unavailable"}
              icon={Tag}
            />
            <KpiCard
              label="Demand Spikes Detected"
              value={data.demand_summary?.products_with_demand_spike ?? "Unavailable"}
              icon={TrendingUp}
            />
            <KpiCard
              label="Promotions Insufficiently Stocked"
              value={data.promotion_summary?.readiness_counts?.insufficient ?? "Unavailable"}
              icon={TrendingDown}
            />
          </div>

          {/* ---- Visualizations ---- */}
          <Card>
            <CardHeader
              title="Sales & Demand Trend"
              subtitle="Confirmed daily sales across the full catalog (actual, measured) -- no catalog-wide daily forecast exists in this system, so no forecast line is drawn here."
            />
            <CardBody>
              {trend.loading && <LoadingState message="Loading sales trend..." />}
              {trend.error && <ErrorState message={trend.error} />}
              {trend.data && (trend.data.error || trendPoints.length === 0) && (
                <EmptyState message={trend.data.error ?? "No confirmed sales history available."} />
              )}
              {trend.data && !trend.data.error && trendPoints.length > 0 && (
                <TrendLineChart points={trendPoints} valueLabel="Units sold (all products)" />
              )}
            </CardBody>
          </Card>

          <Card>
            <CardHeader
              title="Actual vs. Forecast Demand"
              subtitle="Clearly separate figures: one measured from confirmed sales, one estimated by the Demand Forecasting Agent."
            />
            <CardBody>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div className="rounded-lg border border-[var(--ric-border)] bg-[var(--ric-pale-highlight)] p-4">
                  <Badge label="Measured" tone="info" />
                  <p className="mt-2 text-xs text-[var(--ric-text-secondary)]">Actual confirmed sales, last 7 days</p>
                  <p className="mt-1 text-2xl font-semibold text-[var(--ric-text-primary)]">
                    {actualLast7Days !== null ? Math.round(actualLast7Days) : "Unavailable"}
                  </p>
                </div>
                <div className="rounded-lg border border-[var(--ric-border)] p-4">
                  <Badge label="Estimated" tone="neutral" />
                  <p className="mt-2 text-xs text-[var(--ric-text-secondary)]">
                    Forecasted demand, next 7 days (all products)
                  </p>
                  <p className="mt-1 text-2xl font-semibold text-[var(--ric-text-primary)]">
                    {forecastedDemandNext7d ?? "Unavailable"}
                  </p>
                </div>
              </div>
            </CardBody>
          </Card>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader title="Inventory Health Distribution" subtitle="All SKUs, by risk level" />
              <CardBody>
                {data.inventory_summary ? (
                  <RiskBreakdownChart counts={data.inventory_summary.risk_level_counts} />
                ) : (
                  <EmptyState message="Inventory agent unavailable." />
                )}
              </CardBody>
            </Card>

            <Card>
              <CardHeader title="Order Fulfillment Risk" subtitle="Open orders, by risk level" />
              <CardBody>
                {data.fulfillment_summary ? (
                  <RiskBreakdownChart counts={data.fulfillment_summary.risk_counts} />
                ) : (
                  <EmptyState message="Fulfillment agent unavailable." />
                )}
              </CardBody>
            </Card>

            <Card>
              <CardHeader title="Promotion Readiness" subtitle="Upcoming/active promotions, by readiness status" />
              <CardBody>
                {data.promotion_summary ? (
                  <RiskBreakdownChart counts={data.promotion_summary.readiness_counts} />
                ) : (
                  <EmptyState message="Promotion agent unavailable." />
                )}
              </CardBody>
            </Card>

            <Card>
              <CardHeader
                title="Customer-Impacting Operational Issues"
                subtitle="At-risk customer orders, by severity"
              />
              <CardBody>
                {customerImpactRisks.loading && <LoadingState message="Loading..." />}
                {customerImpactRisks.error && <ErrorState message={customerImpactRisks.error} />}
                {cxSeverityCounts && Object.keys(cxSeverityCounts).length > 0 ? (
                  <RiskBreakdownChart counts={cxSeverityCounts} />
                ) : (
                  cxSeverityCounts && <EmptyState message="No customer-impacting issues right now." />
                )}
              </CardBody>
            </Card>
          </div>

          <Card>
            <CardHeader
              title="Stockout Risk by SKU"
              subtitle="Top 10 SKUs by stockout risk, across all stores. Store-level filtering isn't available as a catalog-wide view yet."
            />
            <CardBody>
              {topStockoutRisks.loading && <LoadingState message="Loading..." />}
              {topStockoutRisks.error && <ErrorState message={topStockoutRisks.error} />}
              {topStockoutRisks.data && (
                <DataTable
                  columns={stockoutColumns}
                  rows={topStockoutRisks.data}
                  rowKey={(r) => r.sku}
                  emptyMessage="No SKUs currently at stockout risk."
                />
              )}
            </CardBody>
          </Card>

          {/* ---- Recommended Actions ---- */}
          <Card>
            <CardHeader
              title="Recommended Actions Requiring Human Review"
              subtitle={
                `Combines real, already-computed findings from the Inventory, Promotion, Fulfillment, and ` +
                `Customer Experience agents. "Expected Impact" reads "Not estimated" because no agent in this ` +
                `system computes a dollar-impact estimate -- that is never fabricated here. "Confidence" ` +
                `describes the real basis each agent used, not a numeric score.`
              }
            />
            <CardBody>
              {replenishment.loading ||
              promotionReadiness.loading ||
              fulfillmentPriorities.loading ||
              serviceRecovery.loading ? (
                <LoadingState message="Loading recommended actions..." />
              ) : actionRows.length === 0 ? (
                <EmptyState message="No recommended actions at this time." />
              ) : (
                <div className="space-y-2">
                  {actionRows.length > VISIBLE_ACTION_LIMIT && (
                    <p className="text-xs text-[var(--ric-text-secondary)]">
                      Showing the top {VISIBLE_ACTION_LIMIT} of {actionRows.length} recommended actions, sorted by
                      severity.
                    </p>
                  )}
                  <DataTable columns={actionColumns} rows={visibleActionRows} rowKey={(r) => r.id} />
                </div>
              )}
            </CardBody>
          </Card>

          <DisclaimerFooter />
        </>
      )}
    </div>
  );
}
