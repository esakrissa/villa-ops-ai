"use client";

import { useState, useId } from "react";

interface ToolCallCardProps {
  name: string;
  args: Record<string, unknown>;
  result?: string;
  isStreaming?: boolean;
}

function formatToolName(name: string): string {
  return name
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

function formatValue(value: unknown): string {
  if (typeof value === "string") return value;
  if (value === null || value === undefined) return "—";
  return JSON.stringify(value);
}

function WrenchIcon({ className }: { className?: string }) {
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
        d="M11.42 15.17 17.25 21A2.652 2.652 0 0 0 21 17.25l-5.877-5.877M11.42 15.17l2.496-3.03c.317-.384.74-.626 1.208-.766M11.42 15.17l-4.655 5.653a2.548 2.548 0 1 1-3.586-3.586l6.837-5.63m5.108-.233c.55-.164 1.163-.188 1.743-.14a4.5 4.5 0 0 0 4.486-6.336l-3.276 3.277a3.004 3.004 0 0 1-2.25-2.25l3.276-3.276a4.5 4.5 0 0 0-6.336 4.486c.091 1.076-.071 2.264-.904 2.95l-.102.085m-1.745 1.437L5.909 7.5H4.5L2.25 3.75l1.5-1.5L7.5 4.5v1.409l4.26 4.26m-1.745 1.437 1.745-1.437m6.615 8.206L15.75 15.75M4.867 19.125h.008v.008h-.008v-.008Z"
      />
    </svg>
  );
}

function SpinnerIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none">
      <circle
        className="opacity-25"
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="4"
      />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
      />
    </svg>
  );
}

function CheckIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      strokeWidth={2}
      stroke="currentColor"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="m4.5 12.75 6 6 9-13.5"
      />
    </svg>
  );
}

export function ToolCallCard({
  name,
  args,
  result,
  isStreaming,
}: ToolCallCardProps) {
  const [expanded, setExpanded] = useState(false);
  const contentId = useId();

  const isPending = isStreaming && !result;
  const argEntries = Object.entries(args);

  return (
    <div className="rounded-lg border border-gray-200 bg-white shadow-sm">
      <button
        onClick={() => setExpanded(!expanded)}
        aria-expanded={expanded}
        aria-controls={contentId}
        className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm transition-colors hover:bg-gray-50"
      >
        <WrenchIcon className="h-4 w-4 shrink-0 text-indigo-500" />
        <span className="font-medium text-gray-700">
          {formatToolName(name)}
        </span>
        <span className="ml-auto flex items-center gap-1.5">
          {isPending ? (
            <SpinnerIcon className="h-4 w-4 animate-spin text-amber-500" />
          ) : (
            <CheckIcon className="h-4 w-4 text-green-500" />
          )}
          <svg
            className={`h-4 w-4 text-gray-400 transition-[rotate] duration-200 ${expanded ? "rotate-180" : ""}`}
            fill="none"
            viewBox="0 0 24 24"
            strokeWidth={2}
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="m19.5 8.25-7.5 7.5-7.5-7.5"
            />
          </svg>
        </span>
      </button>

      {expanded && (
        <div id={contentId} className="border-t border-gray-100 px-3 py-2">
          {argEntries.length > 0 && (
            <div className="mb-2">
              <p className="mb-1 text-xs font-medium text-gray-500">
                Parameters
              </p>
              <dl className="space-y-0.5">
                {argEntries.map(([key, value]) => (
                  <div key={key} className="flex gap-2 text-xs">
                    <dt className="shrink-0 font-mono text-gray-500">{key}:</dt>
                    <dd className="truncate text-gray-700">
                      {formatValue(value)}
                    </dd>
                  </div>
                ))}
              </dl>
            </div>
          )}

          {result && (
            <div>
              <p className="mb-1 text-xs font-medium text-gray-500">Result</p>
              <pre className="max-h-48 overflow-auto rounded-md bg-gray-50 p-2 font-mono text-xs whitespace-pre-wrap text-gray-700">
                {result}
              </pre>
            </div>
          )}

          {isPending && (
            <p className="text-xs italic text-gray-400">Running...</p>
          )}
        </div>
      )}
    </div>
  );
}
