"use client";

import { BarChart, Bar, Cell, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import { CHART, ChartEmpty, ChartSkeleton, ChartTooltip, axisProps, gridProps } from "./chartTheme";

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
  const d = payload[0].payload;
  return (
    <ChartTooltip
      title={d.property_name}
      value={`${Number(d.occupancy_rate).toFixed(1)}%`}
      detail={`${d.booked_days} of ${d.total_days} nights booked`}
    />
  );
}

/** "Le Ayu Villa Canggu" → "Le Ayu" — keeps x-axis labels from colliding. */
function shortName(name: string): string {
  const words = name.split(" ");
  const two = words.slice(0, 2).join(" ");
  return two.length <= 11 ? two : words[0];
}

export function OccupancyChart({ data, loading }: OccupancyChartProps) {
  if (loading) return <ChartSkeleton />;
  if (data.length === 0) return <ChartEmpty label="No occupancy data for this period" />;

  const top = Math.max(...data.map((d) => Number(d.occupancy_rate)));

  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart data={data} margin={{ top: 8, right: 4, left: -16, bottom: 0 }} barCategoryGap="22%">
        <CartesianGrid {...gridProps} />
        <XAxis
          dataKey="property_name"
          {...axisProps}
          interval={0}
          tickFormatter={shortName}
        />
        <YAxis domain={[0, 100]} {...axisProps} tickFormatter={(v: number) => `${v}%`} />
        <Tooltip content={<OccupancyTooltip />} cursor={{ fill: "rgb(47 44 37 / 0.04)", radius: 12 }} />
        <Bar
          dataKey="occupancy_rate"
          radius={[10, 10, 10, 10]}
          maxBarSize={56}
          background={{ fill: "#f6f1e8", radius: 10 }}
        >
          {data.map((d) => (
            <Cell key={d.property_name} fill={Number(d.occupancy_rate) === top ? CHART.ink : CHART.inkSoft} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
