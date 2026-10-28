/**
 * Renders DemandForecastEngine.backtest()'s result (embedded in
 * DemandForecastResult.backtest) -- a strictly chronological train/holdout
 * split (never shuffled, no future-data leakage) scoring this agent's
 * weighted moving average against a plain historical-average baseline on
 * real held-out actuals. These are the only forecast accuracy numbers this
 * app ever shows; everywhere else a "forecast" is explicitly an untested
 * estimate. This component only reports the measured MAE/WAPE/bias for
 * each method -- it never claims one method is "better" or that accuracy
 * has "improved," since a single holdout window isn't evidence of that.
 */

import type { BacktestResult } from "@/lib/types";
import { EmptyState } from "@/components/retail/EmptyState";

const REASON_LABELS: Record<string, string> = {
  insufficient_history_for_backtest: "Not enough historical data to hold out a backtest window yet.",
};

export function ForecastErrorMetrics({ backtest }: { backtest: BacktestResult }) {
  if (!backtest.evaluated) {
    const detail =
      backtest.min_days_required != null
        ? ` (needs at least ${backtest.min_days_required} day(s) of confirmed history; ${backtest.history_days_available ?? 0} available).`
        : "";
    return (
      <EmptyState
        message={`${REASON_LABELS[backtest.reason ?? ""] ?? backtest.reason ?? "Backtest not available."}${detail}`}
      />
    );
  }

  const rows = [
    { label: "Weighted moving average (this agent's forecast method)", metrics: backtest.weighted_moving_average },
    { label: "Simple historical average (baseline for comparison)", metrics: backtest.simple_average_baseline },
  ];

  return (
    <div className="space-y-2">
      <p className="text-xs text-[var(--ric-text-secondary)]">
        Measured against {backtest.holdout_days} day(s) of actual holdout sales (
        {backtest.holdout_period?.start} to {backtest.holdout_period?.end}, trained on the preceding{" "}
        {backtest.train_days} day(s)). Lower MAE/WAPE/|bias| indicates a closer fit to that holdout period only --
        not a guarantee of future accuracy.
        {backtest.zero_actual_demand_in_holdout && " The holdout period had zero actual demand; WAPE is undefined."}
      </p>
      <div className="overflow-x-auto rounded-lg border border-[var(--ric-border)]">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="bg-[var(--ric-page-bg)]">
              <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-[var(--ric-text-secondary)]">
                Method
              </th>
              <th className="px-3 py-2 text-right text-xs font-semibold uppercase tracking-wide text-[var(--ric-text-secondary)]">
                MAE
              </th>
              <th className="px-3 py-2 text-right text-xs font-semibold uppercase tracking-wide text-[var(--ric-text-secondary)]">
                WAPE
              </th>
              <th className="px-3 py-2 text-right text-xs font-semibold uppercase tracking-wide text-[var(--ric-text-secondary)]">
                Bias
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--ric-border)]">
            {rows.map((row) => (
              <tr key={row.label}>
                <td className="px-3 py-2 text-[var(--ric-text-primary)]">{row.label}</td>
                <td className="px-3 py-2 text-right text-[var(--ric-text-primary)]">{row.metrics?.mae ?? "--"}</td>
                <td className="px-3 py-2 text-right text-[var(--ric-text-primary)]">
                  {row.metrics?.wape != null ? `${(row.metrics.wape * 100).toFixed(1)}%` : "Undefined"}
                </td>
                <td className="px-3 py-2 text-right text-[var(--ric-text-primary)]">{row.metrics?.bias ?? "--"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
