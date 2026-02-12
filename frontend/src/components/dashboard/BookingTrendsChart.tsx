"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

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
  const data = payload[0].payload;
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-3 shadow-lg">
      <p className="font-medium text-gray-900">{data.month}</p>
      <p className="text-sm text-emerald-600">
        {data.count} booking{data.count !== 1 ? "s" : ""}
      </p>
    </div>
  );
}

export function BookingTrendsChart({ data, loading }: BookingTrendsChartProps) {
  if (loading) {
    return (
      <div className="h-[300px] w-full animate-pulse rounded bg-gray-100" />
    );
  }

  if (data.length === 0) {
    return (
      <div className="flex h-[300px] items-center justify-center text-sm text-gray-500">
        No booking trend data available
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart data={data}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="month" tick={{ fontSize: 12 }} />
        <YAxis allowDecimals={false} tick={{ fontSize: 12 }} />
        <Tooltip content={<TrendsTooltip />} />
        <Bar
          dataKey="count"
          fill="#10b981"
          radius={[4, 4, 0, 0]}
        />
      </BarChart>
    </ResponsiveContainer>
  );
}
