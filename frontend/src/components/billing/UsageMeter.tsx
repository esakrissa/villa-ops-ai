"use client";

interface UsageMeterProps {
  label: string;
  used: number;
  limit: number | null;
  icon?: React.ReactNode;
}

export function UsageMeter({ label, used, limit, icon }: UsageMeterProps) {
  const unlimited = limit === null;
  const percentage = !unlimited && limit > 0 ? Math.min(Math.round((used / limit) * 100), 100) : 0;
  const atLimit = percentage >= 90;
  const nearLimit = percentage >= 70 && !atLimit;

  return (
    <div>
      <div className="flex items-center justify-between">
        <p className="flex items-center gap-2 text-[14px] text-gray-600">
          {icon}
          {label}
        </p>
        {!unlimited && <span className="font-mono text-[11px] text-gray-400">{percentage}%</span>}
      </div>
      <p className="mt-2 flex items-baseline gap-1.5">
        <span className="display text-[44px] leading-none text-ink">{used}</span>
        <span className="text-[14px] text-gray-500">{unlimited ? "used · unlimited" : `of ${limit}`}</span>
      </p>
      {!unlimited && (
        <div className="mt-3 h-1.5 w-full overflow-hidden rounded-full bg-gray-100">
          <div
            className={`h-full rounded-full transition-[width] duration-500 ${atLimit ? "bg-[#b4532a]" : "bg-ink"}`}
            style={{ width: `${percentage}%` }}
          />
        </div>
      )}
      {(atLimit || nearLimit) && (
        <p className={`mt-2 text-[12px] ${atLimit ? "text-[#b4532a]" : "text-gray-500"}`}>
          {atLimit ? "Limit reached. Upgrade for more." : "Approaching your limit."}
        </p>
      )}
    </div>
  );
}
