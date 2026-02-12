"use client";

interface UsageMeterProps {
  label: string;
  used: number;
  limit: number | null;
  icon?: React.ReactNode;
}

export function UsageMeter({ label, used, limit, icon }: UsageMeterProps) {
  if (limit === null) {
    return (
      <div className="space-y-2">
        <div className="flex items-center gap-2 text-sm font-medium text-gray-700">
          {icon}
          <span>{label}</span>
        </div>
        <p className="text-sm text-gray-500">
          <span className="font-semibold text-gray-900">{used}</span> used
          &middot; Unlimited
        </p>
      </div>
    );
  }

  const percentage = limit > 0 ? Math.min(Math.round((used / limit) * 100), 100) : 0;

  let barColor: string;
  let warningText: string | null = null;

  if (percentage >= 90) {
    barColor = "bg-red-500";
    warningText = "Upgrade for more";
  } else if (percentage >= 70) {
    barColor = "bg-amber-500";
    warningText = "Approaching limit";
  } else {
    barColor = "bg-indigo-600";
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 text-sm font-medium text-gray-700">
        {icon}
        <span>{label}</span>
      </div>
      <div className="flex items-baseline justify-between text-sm">
        <p className="text-gray-500">
          <span className="font-semibold text-gray-900">{used}</span> / {limit}{" "}
          used
        </p>
        <span className="text-gray-400">{percentage}%</span>
      </div>
      <div className="h-2 w-full overflow-hidden rounded-full bg-gray-200">
        <div
          className={`h-full rounded-full transition-all ${barColor}`}
          style={{ width: `${percentage}%` }}
        />
      </div>
      {warningText && (
        <p
          className={`text-xs font-medium ${percentage >= 90 ? "text-red-600" : "text-amber-600"}`}
        >
          {warningText}
        </p>
      )}
    </div>
  );
}
