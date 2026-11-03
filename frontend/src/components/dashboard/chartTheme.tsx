/** Shared Recharts styling — hairline grid, mono ticks, dark tooltip. */

export const CHART = {
  ink: "#2f2c25",
  inkSoft: "#d8ccb5",
  lime: "#d5f500",
  grid: "#ece5d9",
  tick: "#9a917f",
};

export const axisProps = {
  axisLine: false,
  tickLine: false,
  tick: { fontSize: 11, fill: CHART.tick, fontFamily: "var(--font-geist-mono)" },
} as const;

export const gridProps = {
  vertical: false,
  stroke: CHART.grid,
  strokeDasharray: "2 4",
} as const;

export function ChartTooltip({
  title,
  value,
  detail,
}: {
  title: string;
  value: string;
  detail?: string;
}) {
  return (
    <div className="min-w-[150px] rounded-2xl bg-coal px-3.5 py-2.5 text-cream shadow-xl">
      <p className="font-mono text-[10px] uppercase tracking-widest text-cream/55">{title}</p>
      <p className="mt-1 font-serif text-[26px] leading-none">{value}</p>
      {detail && <p className="mt-1.5 text-[12px] text-cream/65">{detail}</p>}
    </div>
  );
}

export function ChartSkeleton() {
  return (
    <div className="flex h-[300px] items-end gap-3 px-2 pb-6">
      {[45, 70, 55, 85, 60, 75].map((h, i) => (
        <div key={i} className="flex-1 animate-pulse rounded-t-xl bg-gray-100" style={{ height: `${h}%` }} />
      ))}
    </div>
  );
}

export function ChartEmpty({ label }: { label: string }) {
  return (
    <div className="flex h-[300px] flex-col items-center justify-center gap-2 rounded-2xl bg-gray-50 text-center">
      <p className="eyebrow text-gray-400">No data</p>
      <p className="text-sm text-gray-500">{label}</p>
    </div>
  );
}
