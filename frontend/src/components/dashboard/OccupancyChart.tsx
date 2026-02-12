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

interface OccupancyData {
  property_name: string;
  occupancy_rate: number;
  booked_days: number;
  total_days: number;
}

interface OccupancyChartProps {
  data: OccupancyData[];
  loading: boolean;
}

function OccupancyTooltip({ active, payload }: { active?: boolean; payload?: Array<{ payload: OccupancyData }> }) {
  if (!active || !payload?.[0]) return null;
  const data = payload[0].payload;
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-3 shadow-lg">
      <p className="font-medium text-gray-900">{data.property_name}</p>
      <p className="text-sm text-indigo-600">
        {Number(data.occupancy_rate).toFixed(1)}% occupied
      </p>
      <p className="text-xs text-gray-500">
        {data.booked_days} / {data.total_days} days
      </p>
    </div>
  );
}

export function OccupancyChart({ data, loading }: OccupancyChartProps) {
  if (loading) {
    return (
      <div className="h-[300px] w-full animate-pulse rounded bg-gray-100" />
    );
  }

  if (data.length === 0) {
    return (
      <div className="flex h-[300px] items-center justify-center text-sm text-gray-500">
        No occupancy data available
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart data={data}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis
          dataKey="property_name"
          tick={{ fontSize: 12 }}
          tickFormatter={(name: string) =>
            name.length > 15 ? name.slice(0, 15) + "..." : name
          }
        />
        <YAxis
          domain={[0, 100]}
          tickFormatter={(v: number) => `${v}%`}
          tick={{ fontSize: 12 }}
        />
        <Tooltip content={<OccupancyTooltip />} />
        <Bar
          dataKey="occupancy_rate"
          fill="#6366f1"
          radius={[4, 4, 0, 0]}
        />
      </BarChart>
    </ResponsiveContainer>
  );
}
