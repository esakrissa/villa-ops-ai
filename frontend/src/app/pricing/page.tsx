"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { PricingCard } from "@/components/billing/PricingCard";
import { apiFetch, API_BASE_URL } from "@/lib/api";
import { isAuthenticated } from "@/lib/auth";
import { useSubscription } from "@/lib/hooks/useSubscription";

interface Plan {
  name: string;
  display_name: string;
  max_properties: number | null;
  max_ai_queries_per_month: number | null;
  has_analytics_export: boolean;
  has_notifications: boolean;
  price_monthly_cents: number;
}

const FALLBACK_PLANS: Plan[] = [
  {
    name: "free",
    display_name: "Free",
    max_properties: 1,
    max_ai_queries_per_month: 50,
    has_analytics_export: false,
    has_notifications: false,
    price_monthly_cents: 0,
  },
  {
    name: "pro",
    display_name: "Pro",
    max_properties: 5,
    max_ai_queries_per_month: 500,
    has_analytics_export: true,
    has_notifications: true,
    price_monthly_cents: 2900,
  },
  {
    name: "business",
    display_name: "Business",
    max_properties: null,
    max_ai_queries_per_month: null,
    has_analytics_export: true,
    has_notifications: true,
    price_monthly_cents: 7900,
  },
];

function planFeatures(plan: Plan): string[] {
  const features: string[] = [];

  if (plan.max_properties === null) {
    features.push("Unlimited properties");
  } else {
    features.push(
      `${plan.max_properties === 1 ? "1 property" : `Up to ${plan.max_properties} properties`}`,
    );
  }

  if (plan.max_ai_queries_per_month === null) {
    features.push("Unlimited AI queries");
  } else {
    features.push(`${plan.max_ai_queries_per_month} AI queries/month`);
  }

  if (plan.has_analytics_export) {
    features.push("Full analytics + export");
  } else {
    features.push("Basic analytics");
  }

  if (plan.has_notifications) {
    features.push("Email notifications");
  }

  if (plan.name === "free") {
    features.push("Community support");
  } else if (plan.name === "pro") {
    features.push("Email support");
  } else if (plan.name === "business") {
    features.push("Priority support");
  }

  return features;
}

export default function PricingPage() {
  const [plans, setPlans] = useState<Plan[]>([]);
  const [loading, setLoading] = useState(true);
  const [checkoutLoading, setCheckoutLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [authed, setAuthed] = useState(false);
  const { subscription } = useSubscription();

  useEffect(() => {
    setAuthed(isAuthenticated());
  }, []);

  useEffect(() => {
    fetch(`${API_BASE_URL}/api/v1/billing/plans`)
      .then((res) => res.json())
      .then((data) => setPlans(data.plans))
      .catch(() => setPlans(FALLBACK_PLANS))
      .finally(() => setLoading(false));
  }, []);

  const currentPlanName = subscription?.plan.name;
  const hasActivePaidPlan =
    authed &&
    currentPlanName != null &&
    currentPlanName !== "free" &&
    subscription?.status === "active";

  async function handleSelectPlan(planName: string) {
    if (planName === "free") {
      window.location.href = "/register";
      return;
    }
    if (!authed) {
      window.location.href = "/register";
      return;
    }

    // Paid users: upgrade in-place via /upgrade endpoint (Stripe Subscription.modify)
    if (hasActivePaidPlan) {
      setCheckoutLoading(planName);
      setError(null);
      try {
        await apiFetch<{ plan: string; status: string }>(
          "/api/v1/billing/upgrade",
          {
            method: "POST",
            body: JSON.stringify({ plan: planName }),
          },
        );
        window.location.href = "/dashboard/billing";
      } catch {
        setError("Failed to upgrade plan. Please try again.");
      } finally {
        setCheckoutLoading(null);
      }
      return;
    }

    setCheckoutLoading(planName);
    setError(null);
    try {
      const data = await apiFetch<{ checkout_url: string }>(
        "/api/v1/billing/checkout",
        {
          method: "POST",
          body: JSON.stringify({
            plan: planName,
            success_url: `${window.location.origin}/checkout/success?session_id={CHECKOUT_SESSION_ID}`,
            cancel_url: `${window.location.origin}/pricing`,
          }),
        },
      );
      window.location.href = data.checkout_url;
    } catch {
      setError("Failed to start checkout. Please try again.");
    } finally {
      setCheckoutLoading(null);
    }
  }

  function getCtaLabel(planName: string): string {
    if (!authed) return planName === "free" ? "Get started" : "Sign up";
    if (subscription?.plan.name === planName) return "Current Plan";
    if (hasActivePaidPlan) return "Upgrade";
    return planName === "free" ? "Get started" : "Upgrade";
  }

  return (
    <div className="flex min-h-screen flex-col bg-white">
      {/* Header */}
      <header className="flex items-center justify-between border-b border-gray-200 px-6 py-4">
        <Link href="/" className="text-xl font-bold text-indigo-600">
          VillaOps AI
        </Link>
        <div className="flex items-center gap-3">
          {authed ? (
            <Link
              href="/chat"
              className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-indigo-500"
            >
              Go to app
            </Link>
          ) : (
            <>
              <Link
                href="/login"
                className="rounded-lg px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100"
              >
                Sign in
              </Link>
              <Link
                href="/register"
                className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-indigo-500"
              >
                Get started
              </Link>
            </>
          )}
        </div>
      </header>

      {/* Pricing Content */}
      <main className="flex flex-1 flex-col items-center px-6 py-16">
        <h1 className="text-4xl font-bold tracking-tight text-gray-900 sm:text-5xl">
          Simple, transparent pricing
        </h1>
        <p className="mt-4 max-w-lg text-center text-lg text-gray-500">
          Start for free, upgrade when you need more. No hidden fees.
        </p>

        {error && (
          <div className="mt-6 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}

        {loading ? (
          <div className="mt-16 flex gap-8">
            {[1, 2, 3].map((i) => (
              <div
                key={i}
                className="h-96 w-80 animate-pulse rounded-2xl bg-gray-100"
              />
            ))}
          </div>
        ) : (
          <div className="mt-16 grid max-w-5xl grid-cols-1 gap-8 md:grid-cols-3">
            {plans.map((plan) => (
              <PricingCard
                key={plan.name}
                name={plan.name}
                displayName={plan.display_name}
                priceMonthly={plan.price_monthly_cents}
                features={planFeatures(plan)}
                highlighted={plan.name === "pro"}
                currentPlan={
                  authed && subscription?.plan.name === plan.name
                }
                ctaLabel={getCtaLabel(plan.name)}
                onSelect={() => handleSelectPlan(plan.name)}
                loading={checkoutLoading === plan.name}
              />
            ))}
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-gray-200 py-6 text-center text-sm text-gray-400">
        VillaOps AI &mdash; Built with Next.js, FastAPI, and LangGraph
      </footer>
    </div>
  );
}
