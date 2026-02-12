"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { apiFetch } from "@/lib/api";
import { useSubscription } from "@/lib/hooks/useSubscription";
import {
  formatDate,
  formatCurrency,
  formatStatus,
  STATUS_STYLES,
} from "@/components/dashboard/BookingTable";
import type { Booking, Property, Guest } from "@/lib/hooks/useBookings";

interface OccupancyResponse {
  period_start: string;
  period_end: string;
  properties: {
    property_id: string;
    property_name: string;
    total_days: number;
    booked_days: number;
    occupancy_rate: number;
  }[];
  overall_occupancy_rate: number;
}

interface MetricCardProps {
  title: string;
  value: string;
  subtitle?: string;
  icon: React.ReactNode;
  loading: boolean;
}

function MetricCard({ title, value, subtitle, icon, loading }: MetricCardProps) {
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-gray-500">{title}</p>
          {loading ? (
            <div className="mt-1 h-8 w-20 animate-pulse rounded bg-gray-200" />
          ) : (
            <p className="mt-1 text-3xl font-bold text-gray-900">{value}</p>
          )}
          {subtitle && (
            <p className="mt-1 text-xs text-gray-500">{subtitle}</p>
          )}
        </div>
        <div className="rounded-lg bg-indigo-50 p-3 text-indigo-600">
          {icon}
        </div>
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const { subscription, loading: subLoading } = useSubscription();
  const [propertiesTotal, setPropertiesTotal] = useState<number | null>(null);
  const [bookingsTotal, setBookingsTotal] = useState<number | null>(null);
  const [occupancyRate, setOccupancyRate] = useState<number | null>(null);
  const [recentBookings, setRecentBookings] = useState<Booking[]>([]);
  const [propertyMap, setPropertyMap] = useState<Map<string, string>>(
    new Map(),
  );
  const [guestMap, setGuestMap] = useState<Map<string, string>>(new Map());
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchDashboardData() {
      setLoading(true);
      try {
        const now = new Date();
        const year = now.getFullYear();
        const month = String(now.getMonth() + 1).padStart(2, "0");
        const day = String(now.getDate()).padStart(2, "0");
        const periodStart = `${year}-${month}-01`;
        const periodEnd = `${year}-${month}-${day}`;

        const [propertiesRes, bookingsRes, recentRes, guestsRes] =
          await Promise.all([
            apiFetch<{ items: Property[]; total: number }>(
              "/api/v1/properties?limit=100",
            ),
            apiFetch<{ items: Booking[]; total: number }>(
              `/api/v1/bookings?check_in_from=${periodStart}&check_in_to=${periodEnd}&limit=1`,
            ),
            apiFetch<{ items: Booking[]; total: number }>(
              "/api/v1/bookings?limit=5",
            ),
            apiFetch<{ items: Guest[]; total: number }>(
              "/api/v1/guests?limit=100",
            ),
          ]);

        setPropertiesTotal(propertiesRes.total);
        setBookingsTotal(bookingsRes.total);
        setRecentBookings(recentRes.items);
        setPropertyMap(
          new Map(propertiesRes.items.map((p) => [p.id, p.name])),
        );
        setGuestMap(new Map(guestsRes.items.map((g) => [g.id, g.name])));

        // Occupancy — may fail if no properties exist
        if (propertiesRes.total > 0) {
          try {
            const occupancy = await apiFetch<OccupancyResponse>(
              `/api/v1/analytics/occupancy?period_start=${periodStart}&period_end=${periodEnd}`,
            );
            setOccupancyRate(occupancy.overall_occupancy_rate);
          } catch {
            setOccupancyRate(null);
          }
        }
      } catch {
        // Dashboard load failure — metrics show as "—"
      } finally {
        setLoading(false);
      }
    }

    fetchDashboardData();
  }, []);

  const aiUsed = subscription?.usage.ai_queries_used ?? 0;
  const aiLimit = subscription?.usage.ai_queries_limit;

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <p className="mt-1 text-sm text-gray-500">
          Overview of your villa operations.
        </p>
      </div>

      {/* Metric cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          title="Properties"
          value={propertiesTotal !== null ? String(propertiesTotal) : "\u2014"}
          loading={loading}
          icon={
            <svg
              className="h-6 w-6"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.5}
                d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4"
              />
            </svg>
          }
        />
        <MetricCard
          title="Bookings This Month"
          value={bookingsTotal !== null ? String(bookingsTotal) : "\u2014"}
          loading={loading}
          icon={
            <svg
              className="h-6 w-6"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.5}
                d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"
              />
            </svg>
          }
        />
        <MetricCard
          title="Occupancy Rate"
          value={
            occupancyRate !== null
              ? `${Math.round(occupancyRate * 100)}%`
              : "\u2014"
          }
          subtitle="Current month"
          loading={loading}
          icon={
            <svg
              className="h-6 w-6"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.5}
                d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
              />
            </svg>
          }
        />
        <MetricCard
          title="AI Queries"
          value={
            subLoading
              ? "\u2014"
              : aiLimit
                ? `${aiUsed} / ${aiLimit}`
                : String(aiUsed)
          }
          subtitle={
            subscription ? `${subscription.plan.display_name} plan` : undefined
          }
          loading={subLoading}
          icon={
            <svg
              className="h-6 w-6"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.5}
                d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456z"
              />
            </svg>
          }
        />
      </div>

      {/* Recent bookings */}
      <div className="rounded-lg border border-gray-200 bg-white shadow-sm">
        <div className="flex items-center justify-between border-b border-gray-200 px-6 py-4">
          <h2 className="text-lg font-semibold text-gray-900">
            Recent Bookings
          </h2>
          <Link
            href="/dashboard/bookings"
            className="text-sm font-medium text-indigo-600 hover:text-indigo-500"
          >
            View all &rarr;
          </Link>
        </div>
        {loading ? (
          <div className="divide-y divide-gray-200">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="flex items-center gap-4 px-6 py-4">
                <div className="h-4 w-32 animate-pulse rounded bg-gray-200" />
                <div className="h-4 w-24 animate-pulse rounded bg-gray-200" />
                <div className="h-4 w-40 animate-pulse rounded bg-gray-200" />
                <div className="h-5 w-16 animate-pulse rounded-full bg-gray-200" />
              </div>
            ))}
          </div>
        ) : recentBookings.length === 0 ? (
          <div className="px-6 py-12 text-center">
            <p className="text-sm text-gray-500">No bookings yet.</p>
          </div>
        ) : (
          <div className="divide-y divide-gray-200">
            {recentBookings.map((booking) => (
              <div
                key={booking.id}
                className="flex flex-wrap items-center gap-x-6 gap-y-1 px-6 py-4"
              >
                <span className="min-w-[120px] text-sm font-medium text-gray-900">
                  {guestMap.get(booking.guest_id) || "Unknown Guest"}
                </span>
                <span className="min-w-[120px] text-sm text-gray-600">
                  {propertyMap.get(booking.property_id) || "Unknown Property"}
                </span>
                <span className="text-sm text-gray-500">
                  {formatDate(booking.check_in)} &ndash;{" "}
                  {formatDate(booking.check_out)}
                </span>
                <span
                  className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium ${STATUS_STYLES[booking.status] || "bg-gray-100 text-gray-800"}`}
                >
                  {formatStatus(booking.status)}
                </span>
                {booking.total_price !== null && (
                  <span className="ml-auto text-sm font-medium text-gray-900">
                    {formatCurrency(booking.total_price)}
                  </span>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Quick actions */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Link
          href="/dashboard/bookings"
          className="flex items-center gap-3 rounded-lg border border-gray-200 bg-white p-4 shadow-sm transition-colors hover:bg-gray-50"
        >
          <div className="rounded-lg bg-indigo-50 p-2 text-indigo-600">
            <svg
              className="h-5 w-5"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.5}
                d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"
              />
            </svg>
          </div>
          <div>
            <p className="text-sm font-medium text-gray-900">
              View all bookings
            </p>
            <p className="text-xs text-gray-500">
              Manage and filter bookings
            </p>
          </div>
        </Link>
        <Link
          href="/dashboard/properties"
          className="flex items-center gap-3 rounded-lg border border-gray-200 bg-white p-4 shadow-sm transition-colors hover:bg-gray-50"
        >
          <div className="rounded-lg bg-indigo-50 p-2 text-indigo-600">
            <svg
              className="h-5 w-5"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.5}
                d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4"
              />
            </svg>
          </div>
          <div>
            <p className="text-sm font-medium text-gray-900">
              Manage properties
            </p>
            <p className="text-xs text-gray-500">
              Add or edit your properties
            </p>
          </div>
        </Link>
        <Link
          href="/chat"
          className="flex items-center gap-3 rounded-lg border border-gray-200 bg-white p-4 shadow-sm transition-colors hover:bg-gray-50"
        >
          <div className="rounded-lg bg-indigo-50 p-2 text-indigo-600">
            <svg
              className="h-5 w-5"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.5}
                d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
              />
            </svg>
          </div>
          <div>
            <p className="text-sm font-medium text-gray-900">Go to chat</p>
            <p className="text-xs text-gray-500">
              Ask AI about your operations
            </p>
          </div>
        </Link>
      </div>
    </div>
  );
}
