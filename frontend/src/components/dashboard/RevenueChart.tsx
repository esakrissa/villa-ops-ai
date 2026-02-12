"use client";

import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

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
  const data = payload[0].payload;
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-3 shadow-lg">
      <p className="font-medium text-gray-900">{data.month}</p>
      <p className="text-sm text-indigo-600">
        ${data.revenue.toLocaleString()}
      </p>
    </div>
  );
}

export function RevenueChart({ data, loading }: RevenueChartProps) {
  if (loading) {
    return (
      <div className="h-[300px] w-full animate-pulse rounded bg-gray-100" />
    );
  }

  if (data.length === 0) {
    return (
      <div className="flex h-[300px] items-center justify-center text-sm text-gray-500">
        No revenue data available
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={300}>
      <AreaChart data={data}>
        <defs>
          <linearGradient id="revenueGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3} />
            <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="month" tick={{ fontSize: 12 }} />
        <YAxis
          tickFormatter={(v: number) => `$${v.toLocaleString()}`}
          tick={{ fontSize: 12 }}
        />
        <Tooltip content={<RevenueTooltip />} />
        <Area
          type="monotone"
          dataKey="revenue"
          stroke="#6366f1"
          fill="url(#revenueGradient)"
          strokeWidth={2}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
