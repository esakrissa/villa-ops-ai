"use client";

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

export function PricingCard({
  displayName,
  priceMonthly,
  features,
  highlighted,
  currentPlan,
  ctaLabel,
  onSelect,
  loading,
}: PricingCardProps) {
  const priceDisplay =
    priceMonthly === 0 ? "Free" : `$${(priceMonthly / 100).toFixed(0)}`;

  return (
    <div
      className={`relative flex flex-col rounded-2xl border p-8 ${
        highlighted
          ? "border-indigo-600 shadow-lg ring-1 ring-indigo-600"
          : "border-gray-200"
      }`}
    >
      {highlighted && (
        <span className="mb-4 inline-block rounded-full bg-indigo-100 px-3 py-1 text-xs font-semibold text-indigo-700">
          Most Popular
        </span>
      )}
      <h3 className="text-lg font-semibold text-gray-900">{displayName}</h3>
      <p className="mt-2">
        <span className="text-4xl font-bold text-gray-900">{priceDisplay}</span>
        {priceMonthly > 0 && (
          <span className="text-gray-500">/month</span>
        )}
      </p>
      <ul className="mt-6 flex-1 space-y-3">
        {features.map((f) => (
          <li key={f} className="flex items-start gap-2 text-sm text-gray-600">
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
      <button
        onClick={onSelect}
        disabled={currentPlan || loading}
        className={`mt-8 w-full rounded-lg py-2.5 text-sm font-semibold transition-colors ${
          highlighted
            ? "bg-indigo-600 text-white hover:bg-indigo-500"
            : "border border-gray-300 text-gray-700 hover:bg-gray-50"
        } disabled:cursor-not-allowed disabled:opacity-50`}
      >
        {loading ? "Redirecting..." : currentPlan ? "Current Plan" : ctaLabel}
      </button>
    </div>
  );
}
