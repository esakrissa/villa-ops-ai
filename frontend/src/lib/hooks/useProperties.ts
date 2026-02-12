"use client";

import { useState, useEffect, useCallback } from "react";
import { apiFetch } from "@/lib/api";

export interface Property {
  id: string;
  owner_id: string;
  name: string;
  description: string | null;
  location: string | null;
  property_type: string;
  max_guests: number | null;
  base_price_per_night: string | null;
  amenities: string[] | null;
  status: string;
  created_at: string;
  updated_at: string;
}

interface PropertyListResponse {
  items: Property[];
  total: number;
}

interface UsePropertiesReturn {
  properties: Property[];
  total: number;
  loading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
}

export function useProperties(): UsePropertiesReturn {
  const [properties, setProperties] = useState<Property[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchProperties = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiFetch<PropertyListResponse>(
        "/api/v1/properties?limit=100",
      );
      setProperties(data.items);
      setTotal(data.total);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to load properties",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchProperties();
  }, [fetchProperties]);

  return {
    properties,
    total,
    loading,
    error,
    refetch: fetchProperties,
  };
}
