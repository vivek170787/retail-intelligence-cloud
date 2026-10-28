"use client";

/**
 * Horizontal bar chart of a severity-keyed count breakdown (e.g.
 * InventoryRiskEngine's risk_level_counts), colored with the same
 * severity palette as every badge/table in the app -- not a separate
 * invented chart color scheme. Renders real counts only; never shown
 * for data the caller doesn't actually have.
 */

import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { orderSeverityKeys, severityHex, severityLabel } from "@/lib/severity";

export function RiskBreakdownChart({ counts }: { counts: Record<string, number> }) {
  const keys = orderSeverityKeys(Object.keys(counts)).filter((key) => counts[key] > 0);

  if (keys.length === 0) {
    return <p className="py-6 text-center text-sm text-[var(--ric-text-secondary)]">No risk data to chart.</p>;
  }

  const data = keys.map((key) => ({
    key,
    label: severityLabel(key),
    count: counts[key],
  }));

  return (
    <div className="h-48 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ top: 4, right: 16, bottom: 4, left: 4 }}>
          <CartesianGrid horizontal={false} stroke="var(--ric-border)" />
          <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11, fill: "var(--ric-text-secondary)" }} axisLine={{ stroke: "var(--ric-border)" }} tickLine={false} />
          <YAxis
            type="category"
            dataKey="label"
            width={120}
            tick={{ fontSize: 11, fill: "var(--ric-text-secondary)" }}
            axisLine={{ stroke: "var(--ric-border)" }}
            tickLine={false}
          />
          <Tooltip
            cursor={{ fill: "var(--ric-section-bg)" }}
            contentStyle={{
              fontSize: 12,
              borderRadius: 8,
              border: "1px solid var(--ric-border)",
              boxShadow: "none",
            }}
          />
          <Bar dataKey="count" radius={[0, 3, 3, 0]} barSize={14} isAnimationActive={false}>
            {data.map((entry) => (
              <Cell key={entry.key} fill={severityHex(entry.key)} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
