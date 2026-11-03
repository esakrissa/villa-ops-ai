"use client";

import { CheckIcon } from "@/components/ui/icons";

interface PricingCardProps {
  name: string;
  displayName: string;
  priceMonthly: number;
  features: string[];
  highlighted?: boolean;
  currentPlan?: boolean;
  ctaLabel: string;
  onSelect: () => void;
  loading?: boolean;
}

const BLURBS: Record<string, string> = {
  free: "Try the agent on one villa and see how it fits your day.",
  pro: "For growing portfolios that want the agent on every booking.",
  business: "Unlimited villas, unlimited questions, priority everything.",
};

export function PricingCard({
  name,
  displayName,
  priceMonthly,
  features,
  highlighted,
  currentPlan,
  ctaLabel,
  onSelect,
  loading,
}: PricingCardProps) {
  const price = priceMonthly === 0 ? "$0" : `$${(priceMonthly / 100).toFixed(0)}`;
  const dark = !!highlighted;

  return (
    <div
      className={`relative flex flex-col rounded-[28px] p-7 sm:p-8 ${
        dark ? "bg-coal text-cream shadow-[0_30px_60px_-30px_rgb(31_29_27/0.6)]" : "bg-sand text-ink"
      }`}
    >
      <div className="flex items-center justify-between">
        <h3 className="text-[20px] font-medium tracking-tight">{displayName}</h3>
        {highlighted && (
          <span className="rounded-full bg-lime px-2.5 py-1 font-mono text-[10px] font-semibold uppercase tracking-widest text-coal">
            Most popular
          </span>
        )}
      </div>
      <p className={`mt-2 min-h-[44px] text-[14px] leading-relaxed ${dark ? "text-cream/65" : "text-gray-600"}`}>
        {BLURBS[name] ?? ""}
      </p>

      <p className="mt-6 flex items-baseline gap-1.5">
        <span className="display text-[64px] leading-none">{price}</span>
        <span className={`text-[14px] ${dark ? "text-cream/55" : "text-gray-500"}`}>/ month</span>
      </p>
      <p className={`eyebrow mt-2 ${dark ? "text-cream/45" : "text-gray-400"}`}>
        {priceMonthly === 0 ? "No card required" : "Cancel anytime"}
      </p>

      <button
        type="button"
        onClick={onSelect}
        disabled={currentPlan || loading}
        className={`mt-7 w-full rounded-full py-3 text-[14px] font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-60 ${
          dark ? "bg-lime text-coal hover:bg-lime-deep" : "bg-ink text-cream hover:bg-coal"
        }`}
      >
        {loading ? "Redirecting…" : currentPlan ? "Current plan" : ctaLabel}
      </button>

      <p className={`eyebrow mt-8 ${dark ? "text-cream/45" : "text-gray-500"}`}>Includes</p>
      <ul className="mt-4 flex-1 space-y-3">
        {features.map((f) => (
          <li key={f} className={`flex items-start gap-2.5 text-[14px] ${dark ? "text-cream/85" : "text-gray-700"}`}>
            <span
              className={`mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full ${
                dark ? "bg-lime text-coal" : "bg-ink text-cream"
              }`}
            >
              <CheckIcon className="h-2.5 w-2.5" />
            </span>
            {f}
          </li>
        ))}
      </ul>
    </div>
  );
}
