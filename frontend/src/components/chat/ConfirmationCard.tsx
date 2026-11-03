"use client";

import { useState } from "react";
import { humanizeToolName } from "@/lib/toolLabels";

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

/** Human-in-the-loop approval for destructive tool calls. */
export function ConfirmationCard({ payload, onConfirm, onCancel, isResolved, resolvedAction }: ConfirmationCardProps) {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const disabled = isSubmitting || isResolved;
  const argEntries = Object.entries(payload.args).filter(([key]) => key !== "user_id");

  return (
    <div className="overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-[0_8px_30px_-16px_rgb(47_44_37/0.25)]">
      <div className="flex items-center gap-2 border-b border-gray-100 bg-linen px-4 py-2.5">
        <span className={`h-2 w-2 rounded-full ${isResolved ? "bg-gray-400" : "bg-ink"}`} />
        <p className="eyebrow text-gray-600">{isResolved ? "Decision recorded" : "Approval needed"}</p>
        <span className="ml-auto font-mono text-[11px] text-gray-400">{payload.tool_name}</span>
      </div>

      <div className="px-4 py-3.5">
        <p className="text-[15px] font-medium text-ink">{humanizeToolName(payload.tool_name)}</p>
        <p className="mt-0.5 text-[14px] text-gray-600">{payload.message}</p>

        {argEntries.length > 0 && (
          <dl className="mt-3 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 rounded-xl bg-gray-50 px-3 py-2.5 text-[12.5px]">
            {argEntries.map(([key, value]) => (
              <div key={key} className="contents">
                <dt className="font-mono text-gray-400">{key}</dt>
                <dd className="truncate text-gray-700">{typeof value === "string" ? value : JSON.stringify(value)}</dd>
              </div>
            ))}
          </dl>
        )}

        <div className="mt-4 flex items-center gap-2">
          {isResolved ? (
            <span
              className={`rounded-full px-3 py-1 text-[12px] font-medium ${
                resolvedAction === "approve" ? "bg-ink text-cream" : "bg-gray-100 text-gray-600"
              }`}
            >
              {resolvedAction === "approve" ? "Confirmed" : "Cancelled"}
            </span>
          ) : (
            <>
              <button
                type="button"
                onClick={() => {
                  setIsSubmitting(true);
                  onConfirm();
                }}
                disabled={disabled}
                className="btn-ink !px-4 !py-1.5 !text-[13px] disabled:cursor-not-allowed disabled:opacity-50"
              >
                Confirm
              </button>
              <button
                type="button"
                onClick={() => {
                  setIsSubmitting(true);
                  onCancel();
                }}
                disabled={disabled}
                className="btn-sand !px-4 !py-1.5 !text-[13px] disabled:cursor-not-allowed disabled:opacity-50"
              >
                Cancel
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
