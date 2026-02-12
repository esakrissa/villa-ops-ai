"use client";

import { useState } from "react";
import Link from "next/link";
import { useSubscription } from "@/lib/hooks/useSubscription";
import { apiFetch } from "@/lib/api";
import { PlanBadge } from "@/components/billing/PlanBadge";
import { UsageMeter } from "@/components/billing/UsageMeter";

function formatBillingDate(isoDate: string): string {
  return new Date(isoDate).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

const upgradeOptions: Record<string, { name: string; display: string; price: string }[]> = {
  free: [
    { name: "pro", display: "Pro", price: "$29/mo" },
    { name: "business", display: "Business", price: "$79/mo" },
  ],
  pro: [{ name: "business", display: "Business", price: "$79/mo" }],
  business: [],
};

export default function BillingPage() {
  const { subscription, loading, error, refetch } = useSubscription();
  const [portalLoading, setPortalLoading] = useState(false);
  const [portalError, setPortalError] = useState<string | null>(null);
  const [upgradeLoading, setUpgradeLoading] = useState<string | null>(null);

  async function handlePortal() {
    setPortalLoading(true);
    setPortalError(null);
    try {
      const data = await apiFetch<{ portal_url: string }>(
        "/api/v1/billing/portal",
        {
          method: "POST",
          body: JSON.stringify({
            return_url: `${window.location.origin}/dashboard/billing`,
          }),
        },
      );
      window.location.href = data.portal_url;
    } catch {
      setPortalError(
        "Unable to open billing portal. Please subscribe to a paid plan first.",
      );
    } finally {
      setPortalLoading(false);
    }
  }

  async function handleUpgrade(planName: string) {
    setUpgradeLoading(planName);
    try {
      const data = await apiFetch<{ checkout_url: string }>(
        "/api/v1/billing/checkout",
        {
          method: "POST",
          body: JSON.stringify({
            plan: planName,
            success_url: `${window.location.origin}/checkout/success?session_id={CHECKOUT_SESSION_ID}`,
            cancel_url: `${window.location.origin}/dashboard/billing`,
          }),
        },
      );
      window.location.href = data.checkout_url;
    } catch {
      setPortalError("Failed to start checkout. Please try again.");
    } finally {
      setUpgradeLoading(null);
    }
  }

  if (loading) {
    return (
      <div className="space-y-6">
        <div>
          <div className="h-8 w-64 animate-pulse rounded bg-gray-200" />
          <div className="mt-2 h-4 w-96 animate-pulse rounded bg-gray-200" />
        </div>
        <div className="grid gap-6 lg:grid-cols-2">
          <div className="h-64 animate-pulse rounded-lg border border-gray-200 bg-gray-50" />
          <div className="h-64 animate-pulse rounded-lg border border-gray-200 bg-gray-50" />
        </div>
        <div className="h-20 animate-pulse rounded-lg border border-gray-200 bg-gray-50" />
      </div>
    );
  }

  if (error || !subscription) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">
            Billing & Subscription
          </h1>
        </div>
        <div className="rounded-lg border border-red-200 bg-red-50 p-6">
          <p className="text-sm text-red-700">
            {error || "Failed to load subscription data."}
          </p>
          <button
            onClick={refetch}
            className="mt-3 rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-500"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  const { plan, usage } = subscription;
  const priceDisplay =
    plan.price_monthly_cents === 0
      ? "Free"
      : `$${(plan.price_monthly_cents / 100).toFixed(0)}/month`;
  const upgrades = upgradeOptions[plan.name] ?? [];

  const features = [
    plan.max_properties === null
      ? "Unlimited properties"
      : `Up to ${plan.max_properties} ${plan.max_properties === 1 ? "property" : "properties"}`,
    plan.max_ai_queries_per_month === null
      ? "Unlimited AI queries"
      : `${plan.max_ai_queries_per_month} AI queries/month`,
    ...(plan.has_analytics_export ? ["Analytics export"] : []),
    ...(plan.has_notifications ? ["Email notifications"] : []),
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex-1">
          <h1 className="text-2xl font-bold text-gray-900">
            Billing & Subscription
          </h1>
          <p className="mt-1 text-sm text-gray-500">
            Manage your plan, usage, and billing.
          </p>
        </div>
        <PlanBadge planName={plan.name} displayName={plan.display_name} />
      </div>

      {/* Cancel warning */}
      {subscription.cancel_at_period_end && subscription.current_period_end && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-4">
          <p className="text-sm text-amber-800">
            Your subscription will end on{" "}
            <span className="font-semibold">
              {formatBillingDate(subscription.current_period_end)}
            </span>
            . You&apos;ll be downgraded to the Free plan.{" "}
            <button
              onClick={handlePortal}
              className="font-semibold text-amber-900 underline hover:no-underline"
            >
              Reactivate
            </button>
          </p>
        </div>
      )}

      {portalError && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4">
          <p className="text-sm text-red-700">{portalError}</p>
        </div>
      )}

      {/* Plan + Usage */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Current Plan Card */}
        <div className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
          <h2 className="text-lg font-semibold text-gray-900">Current Plan</h2>

          <div className="mt-4 flex items-baseline gap-3">
            <PlanBadge planName={plan.name} displayName={plan.display_name} />
            <span className="text-2xl font-bold text-gray-900">
              {priceDisplay}
            </span>
          </div>

          <div className="mt-4 space-y-2 text-sm text-gray-600">
            <div className="flex items-center gap-2">
              <span className="text-gray-400">Status:</span>
              <span
                className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${
                  subscription.status === "active"
                    ? "bg-green-100 text-green-700"
                    : subscription.status === "trialing"
                      ? "bg-blue-100 text-blue-700"
                      : "bg-gray-100 text-gray-700"
                }`}
              >
                {subscription.status.charAt(0).toUpperCase() +
                  subscription.status.slice(1)}
              </span>
            </div>

            {subscription.current_period_start &&
              subscription.current_period_end && (
                <>
                  <div>
                    <span className="text-gray-400">Billing period: </span>
                    {formatBillingDate(subscription.current_period_start)} &mdash;{" "}
                    {formatBillingDate(subscription.current_period_end)}
                  </div>
                  <div>
                    <span className="text-gray-400">Next billing: </span>
                    {formatBillingDate(subscription.current_period_end)}
                  </div>
                </>
              )}
          </div>

          <ul className="mt-6 space-y-2">
            {features.map((f) => (
              <li
                key={f}
                className="flex items-start gap-2 text-sm text-gray-600"
              >
                <svg
                  className="mt-0.5 h-4 w-4 shrink-0 text-indigo-600"
                  fill="none"
                  viewBox="0 0 24 24"
                  strokeWidth={2.5}
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M4.5 12.75l6 6 9-13.5"
                  />
                </svg>
                <span>{f}</span>
              </li>
            ))}
          </ul>
        </div>

        {/* Usage Card */}
        <div className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
          <h2 className="text-lg font-semibold text-gray-900">Usage</h2>

          <div className="mt-6 space-y-6">
            <UsageMeter
              label="AI Queries"
              used={usage.ai_queries_used}
              limit={usage.ai_queries_limit}
              icon={
                <svg
                  className="h-4 w-4 text-gray-400"
                  fill="none"
                  viewBox="0 0 24 24"
                  strokeWidth={1.5}
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M8.625 12a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0H8.25m4.125 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0H12m4.125 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 0 1-2.555-.337A5.972 5.972 0 0 1 5.41 20.97a5.969 5.969 0 0 1-.474-.065 4.48 4.48 0 0 0 .978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25Z"
                  />
                </svg>
              }
            />

            <UsageMeter
              label="Properties"
              used={usage.properties_used}
              limit={usage.properties_limit}
              icon={
                <svg
                  className="h-4 w-4 text-gray-400"
                  fill="none"
                  viewBox="0 0 24 24"
                  strokeWidth={1.5}
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M8.25 21v-4.875c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125V21m0 0h4.5V3.545M12.75 21h7.5V10.75M2.25 21h1.5m18 0h-18M2.25 9l4.5-1.636M18.75 3l-1.5.545m0 6.205 3 1m1.5.5-1.5-.5M6.75 7.364V3h-3v18m3-13.636 10.5-3.819"
                  />
                </svg>
              }
            />
          </div>
        </div>
      </div>

      {/* Actions */}
      <div className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
        <div className="flex flex-wrap items-center gap-3">
          {subscription.stripe_subscription_id && (
            <button
              onClick={handlePortal}
              disabled={portalLoading}
              className="rounded-lg border border-gray-300 px-4 py-2.5 text-sm font-semibold text-gray-700 transition-colors hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {portalLoading ? "Opening..." : "Manage Subscription"}
            </button>
          )}

          {upgrades.map((upgrade) => (
            <button
              key={upgrade.name}
              onClick={() => handleUpgrade(upgrade.name)}
              disabled={upgradeLoading === upgrade.name}
              className="rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-indigo-500 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {upgradeLoading === upgrade.name
                ? "Redirecting..."
                : `Upgrade to ${upgrade.display} (${upgrade.price})`}
            </button>
          ))}

          <Link
            href="/pricing"
            className="text-sm font-medium text-indigo-600 hover:text-indigo-500"
          >
            Compare all plans &rarr;
          </Link>
        </div>
      </div>
    </div>
  );
}
