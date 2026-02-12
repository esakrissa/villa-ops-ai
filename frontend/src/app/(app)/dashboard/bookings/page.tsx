"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import { apiFetch } from "@/lib/api";
import { useBookings, type Booking, type Property } from "@/lib/hooks/useBookings";
import { BookingTable } from "@/components/dashboard/BookingTable";

const STATUSES = [
  { value: "", label: "All Statuses" },
  { value: "pending", label: "Pending" },
  { value: "confirmed", label: "Confirmed" },
  { value: "checked_in", label: "Checked In" },
  { value: "checked_out", label: "Checked Out" },
  { value: "cancelled", label: "Cancelled" },
];

function sortBookings(
  bookings: Booking[],
  field: string | null,
  dir: "asc" | "desc",
  propertyMap: Map<string, string>,
  guestMap: Map<string, string>,
): Booking[] {
  if (!field) return bookings;
  return [...bookings].sort((a, b) => {
    let aVal: string | number | null;
    let bVal: string | number | null;

    if (field === "guest") {
      aVal = guestMap.get(a.guest_id) || "";
      bVal = guestMap.get(b.guest_id) || "";
    } else if (field === "property") {
      aVal = propertyMap.get(a.property_id) || "";
      bVal = propertyMap.get(b.property_id) || "";
    } else {
      aVal = a[field as keyof Booking] as string | number | null;
      bVal = b[field as keyof Booking] as string | number | null;
    }

    if (aVal === null) return 1;
    if (bVal === null) return -1;
    if (aVal < bVal) return dir === "asc" ? -1 : 1;
    if (aVal > bVal) return dir === "asc" ? 1 : -1;
    return 0;
  });
}

export default function BookingsPage() {
  const {
    bookings,
    total,
    loading,
    error,
    page,
    setPage,
    filters,
    setFilters,
    propertyMap,
    guestMap,
  } = useBookings(20);

  const [properties, setProperties] = useState<Property[]>([]);
  const [sortField, setSortField] = useState<string | null>(null);
  const [sortDirection, setSortDirection] = useState<"asc" | "desc">("asc");

  useEffect(() => {
    apiFetch<{ items: Property[]; total: number }>(
      "/api/v1/properties?limit=100",
    ).then((res) => setProperties(res.items)).catch(() => {});
  }, []);

  const handleSort = useCallback(
    (field: string) => {
      if (sortField === field) {
        setSortDirection((d) => (d === "asc" ? "desc" : "asc"));
      } else {
        setSortField(field);
        setSortDirection("asc");
      }
    },
    [sortField],
  );

  const sortedBookings = useMemo(
    () => sortBookings(bookings, sortField, sortDirection, propertyMap, guestMap),
    [bookings, sortField, sortDirection, propertyMap, guestMap],
  );

  const limit = 20;
  const totalPages = Math.ceil(total / limit);
  const showingFrom = total === 0 ? 0 : (page - 1) * limit + 1;
  const showingTo = Math.min(page * limit, total);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Bookings</h1>
        <p className="mt-1 text-sm text-gray-500">
          Manage and track all your property bookings.
        </p>
      </div>

      {/* Filter bar */}
      <div className="flex flex-wrap gap-3">
        <select
          value={filters.status || ""}
          onChange={(e) =>
            setFilters({ ...filters, status: e.target.value || undefined })
          }
          className="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-700 shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
        >
          {STATUSES.map((s) => (
            <option key={s.value} value={s.value}>
              {s.label}
            </option>
          ))}
        </select>

        <select
          value={filters.property_id || ""}
          onChange={(e) =>
            setFilters({
              ...filters,
              property_id: e.target.value || undefined,
            })
          }
          className="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-700 shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
        >
          <option value="">All Properties</option>
          {properties.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>

        <div className="flex items-center gap-2">
          <label className="text-sm text-gray-500">From</label>
          <input
            type="date"
            value={filters.check_in_from || ""}
            onChange={(e) =>
              setFilters({
                ...filters,
                check_in_from: e.target.value || undefined,
              })
            }
            className="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-700 shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          />
        </div>

        <div className="flex items-center gap-2">
          <label className="text-sm text-gray-500">To</label>
          <input
            type="date"
            value={filters.check_in_to || ""}
            onChange={(e) =>
              setFilters({
                ...filters,
                check_in_to: e.target.value || undefined,
              })
            }
            className="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-700 shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          />
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Table */}
      <BookingTable
        bookings={sortedBookings}
        loading={loading}
        sortField={sortField}
        sortDirection={sortDirection}
        onSort={handleSort}
        propertyMap={propertyMap}
        guestMap={guestMap}
      />

      {/* Pagination */}
      <div className="flex items-center justify-between">
        <p className="text-sm text-gray-600">
          {total > 0
            ? `Showing ${showingFrom}–${showingTo} of ${total}`
            : "No results"}
        </p>
        <div className="flex gap-2">
          <button
            onClick={() => setPage(page - 1)}
            disabled={page <= 1}
            className="rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 shadow-sm hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
          >
            Previous
          </button>
          <button
            onClick={() => setPage(page + 1)}
            disabled={page >= totalPages}
            className="rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 shadow-sm hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
}
