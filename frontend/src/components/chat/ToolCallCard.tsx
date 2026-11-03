"use client";

import { useId, useState } from "react";
import { CheckIcon, ChevronIcon, SparkIcon } from "@/components/ui/icons";
import { summarizeArgs, toolLabel } from "@/lib/toolLabels";

interface ToolCall {
  name: string;
  args: Record<string, unknown>;
}

function prettyResult(result: string): string {
  try {
    return JSON.stringify(JSON.parse(result), null, 2);
  } catch {
    return result;
  }
}

function Spinner() {
  return (
    <span className="relative flex h-4 w-4 items-center justify-center">
      <span className="absolute h-4 w-4 animate-spin rounded-full border-[1.5px] border-gray-300 border-t-ink" />
    </span>
  );
}

/** One step in the agent's work log — Cursor/Claude style. */
export function ToolCallCard({
  name,
  args,
  result,
  isStreaming,
  isLast,
}: ToolCall & { result?: string; isStreaming?: boolean; isLast?: boolean }) {
  const [expanded, setExpanded] = useState(false);
  const contentId = useId();
  const pending = !!isStreaming && !result;
  const summary = summarizeArgs(args);
  const visibleArgs = Object.entries(args).filter(([k]) => k !== "user_id");

  return (
    <li className="relative pl-7">
      {/* Timeline rail */}
      {!isLast && <span className="absolute bottom-[-6px] left-[7.5px] top-6 w-px bg-gray-200" />}
      <span className="absolute left-0 top-[9px]">
        {pending ? (
          <Spinner />
        ) : (
          <span className="flex h-4 w-4 items-center justify-center rounded-full bg-ink text-cream">
            <CheckIcon className="h-2.5 w-2.5" />
          </span>
        )}
      </span>

      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        aria-expanded={expanded}
        aria-controls={contentId}
        className="group flex w-full items-center gap-2 rounded-lg py-1.5 pr-2 text-left"
      >
        <span className={`shrink-0 text-[14px] ${pending ? "shimmer-text font-medium" : "text-ink"}`}>
          {toolLabel(name, pending)}
        </span>
        {summary && <span className="min-w-0 truncate text-[13px] text-gray-400">{summary}</span>}
        <ChevronIcon
          className={`ml-auto h-3.5 w-3.5 shrink-0 text-gray-400 opacity-0 transition-[opacity,rotate] group-hover:opacity-100 ${
            expanded ? "rotate-180 opacity-100" : ""
          }`}
        />
      </button>

      {expanded && (
        <div id={contentId} className="mb-2 mt-1 overflow-hidden rounded-xl border border-gray-200 bg-white">
          <div className="flex items-center justify-between border-b border-gray-100 px-3 py-2">
            <span className="font-mono text-[11px] text-gray-500">{name}</span>
            <span className="eyebrow !text-[10px] text-gray-400">{pending ? "Running" : "Completed"}</span>
          </div>
          {visibleArgs.length > 0 && (
            <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 px-3 py-2.5 text-[12px]">
              {visibleArgs.map(([k, v]) => (
                <div key={k} className="contents">
                  <dt className="font-mono text-gray-400">{k}</dt>
                  <dd className="truncate font-mono text-gray-700">{typeof v === "string" ? v : JSON.stringify(v)}</dd>
                </div>
              ))}
            </dl>
          )}
          {result && (
            <pre className="max-h-64 overflow-auto border-t border-gray-100 bg-gray-50 px-3 py-2.5 font-mono text-[11.5px] leading-relaxed whitespace-pre-wrap text-gray-700">
              {prettyResult(result)}
            </pre>
          )}
        </div>
      )}
    </li>
  );
}

/** Collapsible group of tool steps: "Used 3 tools" / "Working…". */
export function ToolSteps({
  toolCalls,
  toolResults,
  isStreaming,
}: {
  toolCalls: ToolCall[];
  toolResults?: { name: string; result: string }[];
  isStreaming?: boolean;
}) {
  const running = !!isStreaming && toolCalls.some((_, i) => !toolResults?.[i]?.result);
  const [open, setOpen] = useState(true);
  const count = toolCalls.length;

  return (
    <div className="mb-3">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="group flex items-center gap-2 h-7 rounded-full border border-gray-200 bg-white pl-2 pr-3 text-[13px] text-gray-600 transition-colors hover:border-gray-300 hover:text-ink"
      >
        <SparkIcon className={`h-3.5 w-3.5 ${running ? "text-ink" : "text-gray-500"}`} />
        {running ? (
          <span className="shimmer-text font-medium">Working</span>
        ) : (
          <span>
            Used {count} {count === 1 ? "tool" : "tools"}
          </span>
        )}
        <ChevronIcon className={`h-3 w-3 text-gray-400 transition-[rotate] ${open ? "rotate-180" : ""}`} />
      </button>

      {open && (
        <ol className="mt-2 ml-1">
          {toolCalls.map((tc, i) => (
            <ToolCallCard
              key={i}
              name={tc.name}
              args={tc.args}
              result={toolResults?.[i]?.result}
              isStreaming={isStreaming}
              isLast={i === count - 1}
            />
          ))}
        </ol>
      )}
    </div>
  );
}
