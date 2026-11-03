"use client";

import { useState, useEffect, useCallback } from "react";
import { apiFetch } from "@/lib/api";
import { OccupancyChart } from "@/components/dashboard/OccupancyChart";
import { RevenueChart } from "@/components/dashboard/RevenueChart";
import { BookingTrendsChart } from "@/components/dashboard/BookingTrendsChart";
import type { Booking } from "@/lib/hooks/useBookings";

interface OccupancyProperty {
  property_id: string;
  property_name: string;
  total_days: number;
  booked_days: number;
  occupancy_rate: number;
}

interface OccupancyResponse {
  period_start: string;
  period_end: string;
  properties: OccupancyProperty[];
  overall_occupancy_rate: number;
}

interface RevenueData {
  month: string;
  revenue: number;
}

interface TrendData {
  month: string;
  count: number;
}

function getDefaultDateRange(): { from: string; to: string } {
  const now = new Date();
  const sixMonthsAgo = new Date(now.getFullYear(), now.getMonth() - 5, 1);
  return {
    from: sixMonthsAgo.toISOString().split("T")[0],
    to: now.toISOString().split("T")[0],
  };
}

function formatMonthLabel(key: string): string {
  const [year, month] = key.split("-");
  const date = new Date(parseInt(year), parseInt(month) - 1);
  return date.toLocaleDateString("en-US", { month: "short", year: "numeric" });
}

function aggregateRevenue(bookings: Booking[]): RevenueData[] {
  const monthMap = new Map<string, number>();
  for (const b of bookings) {
    if (b.status === "cancelled" || b.total_price === null) continue;
    const date = new Date(b.check_in);
    const key = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
    // total_price is a Decimal serialized as a string — coerce before adding
    monthMap.set(key, (monthMap.get(key) || 0) + Number(b.total_price));
  }
  return Array.from(monthMap.entries())
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([key, revenue]) => ({
      month: formatMonthLabel(key),
      revenue,
    }));
}

/** Headline numbers beside the trends chart. */
function TrendsSummary({
  data,
  revenue,
  loading,
}: {
  data: TrendData[];
  revenue: RevenueData[];
  loading: boolean;
}) {
  const total = data.reduce((sum, d) => sum + d.count, 0);
  const busiest = data.reduce<TrendData | null>((best, d) => (!best || d.count > best.count ? d : best), null);
  const totalRevenue = revenue.reduce((sum, r) => sum + r.revenue, 0);
  const rows = [
    { label: "Bookings in range", value: String(total) },
    { label: "Busiest month", value: busiest ? busiest.month : "—" },
    { label: "Avg. per month", value: data.length ? (total / data.length).toFixed(1) : "—" },
    { label: "Booked revenue", value: `$${Math.round(totalRevenue).toLocaleString()}` },
  ];

  return (
    <div className="scene-dusk grain flex flex-col justify-between overflow-hidden rounded-[1.5rem] p-6">
      <p className="eyebrow text-cream/70">Summary</p>
      <dl className="glass mt-6 divide-y divide-coal/10 rounded-2xl px-4">
        {rows.map((r) => (
          <div key={r.label} className="flex items-baseline justify-between gap-3 py-3">
            <dt className="text-[13px] text-coal/70">{r.label}</dt>
            <dd className="font-serif text-[24px] leading-none text-coal">
              {loading ? <span className="inline-block h-5 w-12 animate-pulse rounded bg-coal/10" /> : r.value}
            </dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

function aggregateTrends(bookings: Booking[]): TrendData[] {
  const monthMap = new Map<string, number>();
  for (const b of bookings) {
    const date = new Date(b.check_in);
    const key = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
    monthMap.set(key, (monthMap.get(key) || 0) + 1);
  }
  return Array.from(monthMap.entries())
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([key, count]) => ({
      month: formatMonthLabel(key),
      count,
    }));
}

export default function AnalyticsPage() {
  const defaultRange = getDefaultDateRange();
  const [from, setFrom] = useState(defaultRange.from);
  const [to, setTo] = useState(defaultRange.to);

  const [occupancyData, setOccupancyData] = useState<OccupancyProperty[]>([]);
  const [overallOccupancy, setOverallOccupancy] = useState<number | null>(null);
  const [revenueData, setRevenueData] = useState<RevenueData[]>([]);
  const [trendsData, setTrendsData] = useState<TrendData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [occupancyRes, bookingsRes] = await Promise.all([
        apiFetch<OccupancyResponse>(
          `/api/v1/analytics/occupancy?period_start=${from}&period_end=${to}`,
        ),
        apiFetch<{ items: Booking[]; total: number }>(
          `/api/v1/bookings?check_in_from=${from}&check_in_to=${to}&limit=100`,
        ),
      ]);

      setOccupancyData(occupancyRes.properties);
      setOverallOccupancy(occupancyRes.overall_occupancy_rate);
      setRevenueData(aggregateRevenue(bookingsRes.items));
      setTrendsData(aggregateTrends(bookingsRes.items));
    } catch {
      setError("Failed to load analytics data. Please try again.");
    } finally {
      setLoading(false);
    }
  }, [from, to]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return (
    <div className="space-y-8">
      {/* Header + date range */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="display text-[44px] text-ink">Analytics</h1>
          <p className="mt-1 text-sm text-gray-500">
            Insights into your property performance.
            {overallOccupancy !== null && !loading && (
              <span className="ml-2 font-medium text-indigo-600">
                Overall occupancy: {Number(overallOccupancy).toFixed(1)}%
              </span>
            )}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <label htmlFor="from" className="text-sm text-gray-600">
              From
            </label>
            <input
              id="from"
              type="date"
              value={from}
              onChange={(e) => setFrom(e.target.value)}
              className="field"
            />
          </div>
          <div className="flex items-center gap-2">
            <label htmlFor="to" className="text-sm text-gray-600">
              To
            </label>
            <input
              id="to"
              type="date"
              value={to}
              onChange={(e) => setTo(e.target.value)}
              className="field"
            />
          </div>
        </div>
      </div>

      {/* Error state */}
      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Charts */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Occupancy by Property */}
        <div className="panel p-6">
          <h2 className="mb-5 text-[17px] font-medium tracking-tight text-ink">
            Occupancy by Property
          </h2>
          <OccupancyChart
            data={occupancyData.map((p) => ({
              property_name: p.property_name,
              occupancy_rate: Number(p.occupancy_rate),
              booked_days: p.booked_days,
              total_days: p.total_days,
            }))}
            loading={loading}
          />
        </div>

        {/* Monthly Revenue */}
        <div className="panel p-6">
          <h2 className="mb-5 text-[17px] font-medium tracking-tight text-ink">
            Monthly Revenue
          </h2>
          <RevenueChart data={revenueData} loading={loading} />
        </div>
      </div>

      {/* Booking Trends + summary */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="panel p-6 lg:col-span-2">
          <h2 className="mb-5 text-[17px] font-medium tracking-tight text-ink">
            Booking Trends
          </h2>
          <BookingTrendsChart data={trendsData} loading={loading} />
        </div>

        <TrendsSummary data={trendsData} revenue={revenueData} loading={loading} />
      </div>
    </div>
  );
}
