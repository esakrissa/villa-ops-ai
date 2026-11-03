"use client";

import { useState } from "react";
import Link from "next/link";
import { toast } from "sonner";
import { useSubscription } from "@/lib/hooks/useSubscription";
import { apiFetch } from "@/lib/api";
import { UsageMeter } from "@/components/billing/UsageMeter";
import { ConfirmModal } from "@/components/ui/ConfirmModal";
import { CheckIcon } from "@/components/ui/icons";

function formatBillingDate(isoDate: string): string {
  return new Date(isoDate).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

const upgradeOptions: Record<string, { name: string; display: string; price: string; blurb: string }[]> = {
  free: [
    { name: "pro", display: "Pro", price: "$29/mo", blurb: "Up to 5 villas, 500 AI queries, analytics export." },
    { name: "business", display: "Business", price: "$79/mo", blurb: "Unlimited villas and AI queries, priority support." },
  ],
  pro: [{ name: "business", display: "Business", price: "$79/mo", blurb: "Unlimited villas and AI queries, priority support." }],
  business: [],
};

export default function BillingPage() {
  const { subscription, loading, error, refetch } = useSubscription();
  const [portalLoading, setPortalLoading] = useState(false);
  const [upgradeLoading, setUpgradeLoading] = useState<string | null>(null);
  const [confirmPlan, setConfirmPlan] = useState<string | null>(null);

  async function handlePortal() {
    setPortalLoading(true);
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
      toast.error(
        "Unable to open billing portal. Please subscribe to a paid plan first.",
      );
    } finally {
      setPortalLoading(false);
    }
  }

  function handleUpgrade(planName: string) {
    const isPaidUser =
      subscription?.stripe_subscription_id &&
      subscription?.status === "active" &&
      subscription?.plan.name !== "free";

    if (isPaidUser) {
      setConfirmPlan(planName);
      return;
    }

    doUpgrade(planName);
  }

  async function doUpgrade(planName: string) {
    const upgrade = upgradeOptions[subscription?.plan.name ?? ""]?.find(
      (u) => u.name === planName,
    );
    const isPaidUser =
      subscription?.stripe_subscription_id &&
      subscription?.status === "active" &&
      subscription?.plan.name !== "free";

    setUpgradeLoading(planName);
    try {
      if (isPaidUser) {
        await apiFetch<{ plan: string; status: string }>(
          "/api/v1/billing/upgrade",
          {
            method: "POST",
            body: JSON.stringify({ plan: planName }),
          },
        );
        toast.success(`Successfully upgraded to ${upgrade?.display ?? planName}!`);
        refetch();
        return;
      }

      // Free users: create a new checkout session
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
      toast.error("Failed to upgrade plan. Please try again.");
    } finally {
      setUpgradeLoading(null);
    }
  }

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="h-14 w-72 animate-pulse rounded-2xl bg-gray-100" />
        <div className="grid gap-4 lg:grid-cols-5">
          <div className="h-80 animate-pulse rounded-[28px] bg-gray-100 lg:col-span-3" />
          <div className="h-80 animate-pulse rounded-[28px] bg-gray-100 lg:col-span-2" />
        </div>
      </div>
    );
  }

  if (error || !subscription) {
    return (
      <div className="space-y-6">
        <h1 className="display text-[44px] text-ink">Billing</h1>
        <div className="panel p-6">
          <p className="text-sm text-red-700">{error || "Failed to load subscription data."}</p>
          <button type="button" onClick={refetch} className="btn-ink mt-4 !py-2">
            Retry
          </button>
        </div>
      </div>
    );
  }

  const { plan, usage } = subscription;
  const price = plan.price_monthly_cents === 0 ? "$0" : `$${(plan.price_monthly_cents / 100).toFixed(0)}`;
  const upgrades = upgradeOptions[plan.name] ?? [];
  const features = [
    plan.max_properties === null
      ? "Unlimited properties"
      : `Up to ${plan.max_properties} ${plan.max_properties === 1 ? "property" : "properties"}`,
    plan.max_ai_queries_per_month === null
      ? "Unlimited AI queries"
      : `${plan.max_ai_queries_per_month} AI queries / month`,
    ...(plan.has_analytics_export ? ["Analytics export"] : []),
    ...(plan.has_notifications ? ["Email notifications"] : []),
  ];

  const confirmUpgrade = confirmPlan
    ? upgradeOptions[plan.name]?.find((u) => u.name === confirmPlan)
    : null;

  return (
    <div className="space-y-6">
      <ConfirmModal
        open={!!confirmPlan}
        title={`Upgrade to ${confirmUpgrade?.display ?? ""}`}
        description={`Your plan will change to ${confirmUpgrade?.display ?? ""} at ${confirmUpgrade?.price ?? ""}. The prorated difference will be charged to your payment method immediately.`}
        confirmLabel="Upgrade now"
        cancelLabel="Cancel"
        onConfirm={() => {
          const p = confirmPlan!;
          setConfirmPlan(null);
          doUpgrade(p);
        }}
        onCancel={() => setConfirmPlan(null)}
      />

      {/* Header */}
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="eyebrow text-gray-500">Billing</p>
          <h1 className="display mt-2 text-[44px] text-ink">
            Plan &amp; <em>usage</em>.
          </h1>
        </div>
        <Link href="/pricing" className="btn-sand !py-2">
          Compare all plans
        </Link>
      </div>

      {/* Cancel warning */}
      {subscription.cancel_at_period_end && subscription.current_period_end && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl bg-linen px-5 py-4 text-[14px] text-ink">
          <p>
            Your subscription ends on <strong>{formatBillingDate(subscription.current_period_end)}</strong>. You&apos;ll
            move to the Free plan after that.
          </p>
          <button type="button" onClick={handlePortal} className="btn-ink !py-1.5 !text-[13px]">
            Reactivate
          </button>
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-5">
        {/* Current plan */}
        <section className="flex flex-col rounded-[28px] bg-coal p-7 text-cream lg:col-span-3">
          <div className="flex items-center justify-between">
            <p className="eyebrow text-cream/50">Current plan</p>
            <span className="rounded-full bg-white/10 px-3 py-1 text-[12px] capitalize text-cream/85">
              {subscription.status}
            </span>
          </div>
          <div className="mt-6 flex flex-wrap items-end justify-between gap-4">
            <h2 className="display text-[72px] leading-none">{plan.display_name}</h2>
            <p className="flex items-baseline gap-1.5">
              <span className="display text-[44px] leading-none">{price}</span>
              <span className="text-[14px] text-cream/55">/ month</span>
            </p>
          </div>

          {subscription.current_period_start && subscription.current_period_end && (
            <p className="mt-3 text-[13px] text-cream/60">
              Billing period {formatBillingDate(subscription.current_period_start)} –{" "}
              {formatBillingDate(subscription.current_period_end)} · Renews{" "}
              {formatBillingDate(subscription.current_period_end)}
            </p>
          )}

          <ul className="mt-8 grid gap-3 border-t border-white/10 pt-6 sm:grid-cols-2">
            {features.map((f) => (
              <li key={f} className="flex items-center gap-2.5 text-[14px] text-cream/85">
                <span className="flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-cream text-coal">
                  <CheckIcon className="h-2.5 w-2.5" />
                </span>
                {f}
              </li>
            ))}
          </ul>

          {subscription.stripe_subscription_id && (
            <button
              type="button"
              onClick={handlePortal}
              disabled={portalLoading}
              className="mt-8 self-start rounded-full bg-cream px-5 py-2.5 text-[14px] font-medium text-coal transition-colors hover:bg-white disabled:cursor-not-allowed disabled:opacity-60"
            >
              {portalLoading ? "Opening…" : "Manage subscription"}
            </button>
          )}
        </section>

        {/* Usage */}
        <section className="panel flex flex-col p-7 lg:col-span-2">
          <p className="eyebrow text-gray-500">This month</p>
          <div className="mt-6 flex flex-1 flex-col justify-between gap-8">
            <UsageMeter label="AI queries" used={usage.ai_queries_used} limit={usage.ai_queries_limit} />
            <UsageMeter label="Properties" used={usage.properties_used} limit={usage.properties_limit} />
          </div>
        </section>
      </div>

      {/* Upgrade options */}
      {upgrades.length > 0 && (
        <div className="grid gap-4 md:grid-cols-2">
          {upgrades.map((upgrade) => (
            <div key={upgrade.name} className="flex flex-col justify-between gap-6 rounded-[28px] bg-sand p-7">
              <div>
                <div className="flex items-baseline justify-between gap-3">
                  <h3 className="display text-[36px] leading-none text-ink">{upgrade.display}</h3>
                  <span className="text-[14px] text-gray-600">{upgrade.price}</span>
                </div>
                <p className="mt-3 text-[14px] text-gray-600">{upgrade.blurb}</p>
              </div>
              <button
                type="button"
                onClick={() => handleUpgrade(upgrade.name)}
                disabled={upgradeLoading === upgrade.name}
                className="btn-ink self-start disabled:cursor-not-allowed disabled:opacity-60"
              >
                {upgradeLoading === upgrade.name ? "Upgrading…" : `Upgrade to ${upgrade.display}`}
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
