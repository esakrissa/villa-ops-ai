"use client";

import { BarChart, Bar, Cell, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import { CHART, ChartEmpty, ChartSkeleton, ChartTooltip, axisProps, gridProps } from "./chartTheme";

interface TrendData {
  month: string;
  count: number;
}

interface BookingTrendsChartProps {
  data: TrendData[];
  loading: boolean;
}

function TrendsTooltip({ active, payload }: { active?: boolean; payload?: Array<{ payload: TrendData }> }) {
  if (!active || !payload?.[0]) return null;
  const d = payload[0].payload;
  return <ChartTooltip title={d.month} value={String(d.count)} detail={`booking${d.count !== 1 ? "s" : ""}`} />;
}

export function BookingTrendsChart({ data, loading }: BookingTrendsChartProps) {
  if (loading) return <ChartSkeleton />;
  if (data.length === 0) return <ChartEmpty label="No bookings in this period" />;

  const last = data.length - 1;

  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart data={data} margin={{ top: 8, right: 4, left: -24, bottom: 0 }} barCategoryGap="12%">
        <CartesianGrid {...gridProps} />
        <XAxis dataKey="month" {...axisProps} />
        <YAxis allowDecimals={false} {...axisProps} />
        <Tooltip content={<TrendsTooltip />} cursor={{ fill: "rgb(47 44 37 / 0.04)", radius: 12 }} />
        <Bar dataKey="count" radius={[12, 12, 12, 12]} maxBarSize={88} background={{ fill: "#f6f1e8", radius: 12 }}>
          {data.map((d, i) => (
            <Cell key={d.month} fill={i === last ? CHART.lime : CHART.inkSoft} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
