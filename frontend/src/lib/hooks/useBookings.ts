"use client";

import { useState, useEffect, useCallback } from "react";
import { apiFetch } from "@/lib/api";

export interface Booking {
  id: string;
  property_id: string;
  guest_id: string;
  check_in: string;
  check_out: string;
  num_guests: number;
  status: "pending" | "confirmed" | "checked_in" | "checked_out" | "cancelled";
  total_price: number | null;
  special_requests: string | null;
  created_at: string;
  updated_at: string;
}

export interface BookingFilters {
  status?: string;
  property_id?: string;
  check_in_from?: string;
  check_in_to?: string;
}

interface BookingListResponse {
  items: Booking[];
  total: number;
}

export interface Property {
  id: string;
  name: string;
  status: string;
}

export interface Guest {
  id: string;
  name: string;
  email: string;
}

interface UseBookingsReturn {
  bookings: Booking[];
  total: number;
  loading: boolean;
  error: string | null;
  page: number;
  setPage: (page: number) => void;
  filters: BookingFilters;
  setFilters: (filters: BookingFilters) => void;
  refetch: () => Promise<void>;
  propertyMap: Map<string, string>;
  guestMap: Map<string, string>;
}

export function useBookings(limit: number = 20): UseBookingsReturn {
  const [bookings, setBookings] = useState<Booking[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [filters, setFiltersState] = useState<BookingFilters>({});
  const [propertyMap, setPropertyMap] = useState<Map<string, string>>(
    new Map(),
  );
  const [guestMap, setGuestMap] = useState<Map<string, string>>(new Map());

  const setFilters = useCallback((newFilters: BookingFilters) => {
    setFiltersState(newFilters);
    setPage(1);
  }, []);

  const fetchLookups = useCallback(async () => {
    try {
      const [propertiesRes, guestsRes] = await Promise.all([
        apiFetch<{ items: Property[]; total: number }>(
          "/api/v1/properties?limit=100",
        ),
        apiFetch<{ items: Guest[]; total: number }>(
          "/api/v1/guests?limit=100",
        ),
      ]);
      setPropertyMap(
        new Map(propertiesRes.items.map((p) => [p.id, p.name])),
      );
      setGuestMap(new Map(guestsRes.items.map((g) => [g.id, g.name])));
    } catch {
      // Lookup failure is non-critical — table will show IDs instead of names
    }
  }, []);

  const fetchBookings = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      const skip = (page - 1) * limit;
      params.set("skip", String(skip));
      params.set("limit", String(limit));

      if (filters.status) params.set("status", filters.status);
      if (filters.property_id) params.set("property_id", filters.property_id);
      if (filters.check_in_from)
        params.set("check_in_from", filters.check_in_from);
      if (filters.check_in_to) params.set("check_in_to", filters.check_in_to);

      const data = await apiFetch<BookingListResponse>(
        `/api/v1/bookings?${params.toString()}`,
      );
      setBookings(data.items);
      setTotal(data.total);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to load bookings",
      );
    } finally {
      setLoading(false);
    }
  }, [page, limit, filters]);

  useEffect(() => {
    fetchLookups();
  }, [fetchLookups]);

  useEffect(() => {
    fetchBookings();
  }, [fetchBookings]);

  return {
    bookings,
    total,
    loading,
    error,
    page,
    setPage,
    filters,
    setFilters,
    refetch: fetchBookings,
    propertyMap,
    guestMap,
  };
}
