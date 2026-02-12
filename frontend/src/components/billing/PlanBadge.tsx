"use client";

interface PlanBadgeProps {
  planName: string;
  displayName: string;
}

const planColors: Record<string, string> = {
  free: "bg-gray-100 text-gray-700",
  pro: "bg-indigo-100 text-indigo-700",
  business: "bg-amber-100 text-amber-700",
};

export function PlanBadge({ planName, displayName }: PlanBadgeProps) {
  const colors = planColors[planName] ?? planColors.free;

  return (
    <span
      className={`inline-block rounded-full px-3 py-1 text-sm font-semibold ${colors}`}
    >
      {displayName}
    </span>
  );
}
