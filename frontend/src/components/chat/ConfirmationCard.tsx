"use client";

import { useState } from "react";

interface ConfirmationPayload {
  type: string;
  tool_name: string;
  args: Record<string, unknown>;
  message: string;
}

interface ConfirmationCardProps {
  payload: ConfirmationPayload;
  onConfirm: () => void;
  onCancel: () => void;
  isResolved?: boolean;
  resolvedAction?: "approve" | "cancel";
}

function formatToolName(name: string): string {
  return name
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

function WarningIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      strokeWidth={1.5}
      stroke="currentColor"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z"
      />
    </svg>
  );
}

export function ConfirmationCard({
  payload,
  onConfirm,
  onCancel,
  isResolved,
  resolvedAction,
}: ConfirmationCardProps) {
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleConfirm = () => {
    setIsSubmitting(true);
    onConfirm();
  };

  const handleCancel = () => {
    setIsSubmitting(true);
    onCancel();
  };

  const disabled = isSubmitting || isResolved;

  // Build a readable summary from the args
  const argEntries = Object.entries(payload.args).filter(
    ([key]) => key !== "user_id",
  );

  return (
    <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 shadow-sm">
      <div className="mb-2 flex items-start gap-2">
        <WarningIcon className="mt-0.5 h-5 w-5 shrink-0 text-amber-500" />
        <div>
          <p className="text-sm font-semibold text-amber-800">
            {formatToolName(payload.tool_name)}
          </p>
          <p className="mt-0.5 text-sm text-amber-700">{payload.message}</p>
        </div>
      </div>

      {argEntries.length > 0 && (
        <div className="mb-3 ml-7 rounded-md bg-white/60 px-2.5 py-1.5">
          <dl className="space-y-0.5">
            {argEntries.map(([key, value]) => (
              <div key={key} className="flex gap-2 text-xs">
                <dt className="shrink-0 font-mono text-amber-600">{key}:</dt>
                <dd className="truncate text-amber-800">
                  {typeof value === "string" ? value : JSON.stringify(value)}
                </dd>
              </div>
            ))}
          </dl>
        </div>
      )}

      {isResolved ? (
        <div className="ml-7">
          <span
            className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
              resolvedAction === "approve"
                ? "bg-red-100 text-red-700"
                : "bg-gray-100 text-gray-600"
            }`}
          >
            {resolvedAction === "approve" ? "Confirmed" : "Cancelled"}
          </span>
        </div>
      ) : (
        <div className="ml-7 flex gap-2">
          <button
            onClick={handleConfirm}
            disabled={disabled}
            className="rounded-md bg-red-600 px-3 py-1.5 text-xs font-medium text-white shadow-sm transition-colors hover:bg-red-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            Confirm
          </button>
          <button
            onClick={handleCancel}
            disabled={disabled}
            className="rounded-md border border-gray-300 bg-white px-3 py-1.5 text-xs font-medium text-gray-700 shadow-sm transition-colors hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
          >
            Cancel
          </button>
        </div>
      )}
    </div>
  );
}
