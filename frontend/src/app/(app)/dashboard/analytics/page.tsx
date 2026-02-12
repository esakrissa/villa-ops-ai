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
    monthMap.set(key, (monthMap.get(key) || 0) + b.total_price);
  }
  return Array.from(monthMap.entries())
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([key, revenue]) => ({
      month: formatMonthLabel(key),
      revenue,
    }));
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
          <h1 className="text-2xl font-bold text-gray-900">Analytics</h1>
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
              className="rounded-md border border-gray-300 px-3 py-1.5 text-sm shadow-sm focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 focus:outline-none"
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
              className="rounded-md border border-gray-300 px-3 py-1.5 text-sm shadow-sm focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 focus:outline-none"
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
        <div className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
          <h2 className="mb-4 text-lg font-semibold text-gray-900">
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
        <div className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
          <h2 className="mb-4 text-lg font-semibold text-gray-900">
            Monthly Revenue
          </h2>
          <RevenueChart data={revenueData} loading={loading} />
        </div>
      </div>

      {/* Booking Trends — full width */}
      <div className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
        <h2 className="mb-4 text-lg font-semibold text-gray-900">
          Booking Trends
        </h2>
        <BookingTrendsChart data={trendsData} loading={loading} />
      </div>
    </div>
  );
}
