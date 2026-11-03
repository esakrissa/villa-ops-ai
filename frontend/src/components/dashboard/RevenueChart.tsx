"use client";

import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import { CHART, ChartEmpty, ChartSkeleton, ChartTooltip, axisProps, gridProps } from "./chartTheme";

interface RevenueData {
  month: string;
  revenue: number;
}

interface RevenueChartProps {
  data: RevenueData[];
  loading: boolean;
}

function RevenueTooltip({ active, payload }: { active?: boolean; payload?: Array<{ payload: RevenueData }> }) {
  if (!active || !payload?.[0]) return null;
  const d = payload[0].payload;
  return <ChartTooltip title={d.month} value={`$${d.revenue.toLocaleString()}`} detail="Booked revenue" />;
}

function compactUsd(v: number): string {
  return v >= 1000 ? `$${(v / 1000).toFixed(v >= 10000 ? 0 : 1)}k` : `$${v}`;
}

export function RevenueChart({ data, loading }: RevenueChartProps) {
  if (loading) return <ChartSkeleton />;
  if (data.length === 0) return <ChartEmpty label="No revenue in this period" />;

  return (
    <ResponsiveContainer width="100%" height={300}>
      <AreaChart data={data} margin={{ top: 12, right: 8, left: -8, bottom: 0 }}>
        <defs>
          <linearGradient id="revenueFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={CHART.ink} stopOpacity={0.14} />
            <stop offset="100%" stopColor={CHART.ink} stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid {...gridProps} />
        <XAxis dataKey="month" {...axisProps} />
        <YAxis {...axisProps} tickFormatter={compactUsd} />
        <Tooltip content={<RevenueTooltip />} cursor={{ stroke: CHART.ink, strokeOpacity: 0.15, strokeDasharray: "3 3" }} />
        <Area
          type="monotone"
          dataKey="revenue"
          stroke={CHART.ink}
          strokeWidth={2}
          fill="url(#revenueFill)"
          dot={false}
          activeDot={{ r: 6, fill: CHART.lime, stroke: CHART.ink, strokeWidth: 2 }}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
