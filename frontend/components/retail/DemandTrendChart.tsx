"use client";

/**
 * Two-series line chart: confirmed historical daily sales (measured) vs.
 * the Demand Forecasting Agent's own flat-rate forecast (estimated), for
 * one SKU. Mirrors dashboard/pages/1_Inventory_and_Demand.py's
 * `px.line(..., color="series")` chart exactly -- same two series, same
 * "historical" vs "forecast" distinction, just rendered with Recharts
 * instead of Plotly. The forecast series is only ever drawn when the
 * caller actually has one; this component never fabricates a forecast
 * line from historical data alone.
 */

import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

export interface DemandTrendPoint {
  date: string;
  historical?: number;
  forecast?: number;
}

export function DemandTrendChart({ points }: { points: DemandTrendPoint[] }) {
  if (points.length === 0) {
    return <p className="py-6 text-center text-sm text-[var(--ric-text-secondary)]">No trend data available.</p>;
  }

  return (
    <div className="h-64 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={points} margin={{ top: 8, right: 16, bottom: 4, left: 4 }}>
          <CartesianGrid vertical={false} stroke="var(--ric-border)" />
          <XAxis
            dataKey="date"
            tick={{ fontSize: 11, fill: "#5b6472" }}
            axisLine={{ stroke: "#e2e5eb" }}
            tickLine={false}
            minTickGap={24}
          />
          <YAxis
            allowDecimals={false}
            tick={{ fontSize: 11, fill: "#5b6472" }}
            axisLine={{ stroke: "#e2e5eb" }}
            tickLine={false}
            width={40}
          />
          <Tooltip
            contentStyle={{ fontSize: 12, borderRadius: 6, border: "1px solid #e2e5eb", boxShadow: "none" }}
          />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          <Line
            type="monotone"
            dataKey="historical"
            name="Historical (measured)"
            stroke="#2f5fdb"
            strokeWidth={2}
            dot={false}
            isAnimationActive={false}
            connectNulls={false}
          />
          <Line
            type="monotone"
            dataKey="forecast"
            name="Forecast (estimated)"
            stroke="#f57c00"
            strokeWidth={2}
            strokeDasharray="4 3"
            dot={false}
            isAnimationActive={false}
            connectNulls={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
