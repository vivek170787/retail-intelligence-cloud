"use client";

/**
 * Line chart for a real date/value series (e.g. catalog-wide confirmed
 * daily sales). No forecast line is drawn unless a forecast series is
 * explicitly passed -- there is no catalog-wide daily forecast in this
 * system, so this never implies one that doesn't exist.
 */

import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

export interface TrendPoint {
  date: string;
  value: number;
}

export function TrendLineChart({ points, valueLabel = "Units" }: { points: TrendPoint[]; valueLabel?: string }) {
  if (points.length === 0) {
    return <p className="py-6 text-center text-sm text-[var(--ric-text-secondary)]">No trend data available.</p>;
  }

  return (
    <div className="h-56 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={points} margin={{ top: 8, right: 16, bottom: 4, left: 4 }}>
          <CartesianGrid vertical={false} stroke="var(--ric-border)" />
          <XAxis
            dataKey="date"
            tick={{ fontSize: 11, fill: "var(--ric-text-secondary)" }}
            axisLine={{ stroke: "var(--ric-border)" }}
            tickLine={false}
            minTickGap={24}
          />
          <YAxis
            allowDecimals={false}
            tick={{ fontSize: 11, fill: "var(--ric-text-secondary)" }}
            axisLine={{ stroke: "var(--ric-border)" }}
            tickLine={false}
            width={40}
          />
          <Tooltip
            formatter={(value) => [value, valueLabel] as [typeof value, string]}
            contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid var(--ric-border)", boxShadow: "none" }}
          />
          <Line
            type="monotone"
            dataKey="value"
            stroke="var(--ric-primary)"
            strokeWidth={2}
            dot={false}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
