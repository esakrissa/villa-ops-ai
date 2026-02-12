"use client";

import { useState, useEffect, useCallback } from "react";
import { apiFetch } from "@/lib/api";
import { isAuthenticated } from "@/lib/auth";

interface Plan {
  name: string;
  display_name: string;
  max_properties: number | null;
  max_ai_queries_per_month: number | null;
  has_analytics_export: boolean;
  has_notifications: boolean;
  price_monthly_cents: number;
}

interface Usage {
  ai_queries_used: number;
  ai_queries_limit: number | null;
  properties_used: number;
  properties_limit: number | null;
}

interface Subscription {
  plan: Plan;
  status: string;
  stripe_subscription_id: string | null;
  current_period_start: string | null;
  current_period_end: string | null;
  cancel_at_period_end: boolean;
  usage: Usage;
}

interface UseSubscriptionReturn {
  subscription: Subscription | null;
  loading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
}

export function useSubscription(): UseSubscriptionReturn {
  const [subscription, setSubscription] = useState<Subscription | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchSubscription = useCallback(async () => {
    if (!isAuthenticated()) {
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const data = await apiFetch<Subscription>(
        "/api/v1/billing/subscription",
      );
      setSubscription(data);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to load subscription",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSubscription();
  }, [fetchSubscription]);

  return { subscription, loading, error, refetch: fetchSubscription };
}

export type { Plan, Usage, Subscription };
