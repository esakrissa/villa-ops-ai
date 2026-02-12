"use client";

import type { ChatMessage } from "@/lib/hooks/useChat";

interface MessageBubbleProps {
  message: ChatMessage;
}

function ToolCallBadge({
  name,
  args,
}: {
  name: string;
  args: Record<string, unknown>;
}) {
  const argsPreview = Object.entries(args)
    .slice(0, 3)
    .map(([k, v]) => `${k}: ${typeof v === "string" ? v : JSON.stringify(v)}`)
    .join(", ");

  return (
    <div className="mt-2 inline-flex items-center gap-1.5 rounded-md border border-indigo-200 bg-indigo-50 px-2.5 py-1 text-xs text-indigo-700">
      <svg
        className="h-3.5 w-3.5 shrink-0"
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
      <span className="font-medium">{name}</span>
      {argsPreview && (
        <span className="text-indigo-500">({argsPreview})</span>
      )}
    </div>
  );
}

function ToolResultDisplay({
  name,
  result,
}: {
  name: string;
  result: string;
}) {
  return (
    <div className="mt-1 rounded-md border border-gray-200 bg-gray-50 p-2 text-xs">
      <span className="font-medium text-gray-500">{name} result:</span>
      <pre className="mt-1 max-h-32 overflow-auto whitespace-pre-wrap font-mono text-gray-700">
        {result}
      </pre>
    </div>
  );
}

function StreamingCursor() {
  return (
    <span className="ml-0.5 inline-block h-4 w-0.5 animate-pulse bg-gray-400" />
  );
}

function TypingDots() {
  return (
    <div className="flex items-center gap-1 py-1">
      <span className="h-2 w-2 animate-bounce rounded-full bg-gray-400 [animation-delay:0ms]" />
      <span className="h-2 w-2 animate-bounce rounded-full bg-gray-400 [animation-delay:150ms]" />
      <span className="h-2 w-2 animate-bounce rounded-full bg-gray-400 [animation-delay:300ms]" />
    </div>
  );
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === "user";
  const isTool = message.role === "tool";

  if (isUser) {
    return (
      <div className="flex justify-end">
        <div className="max-w-[75%] rounded-2xl rounded-br-md bg-indigo-600 px-4 py-2.5 text-white shadow-sm">
          <p className="whitespace-pre-wrap text-sm">{message.content}</p>
        </div>
      </div>
    );
  }

  if (isTool) {
    return (
      <div className="flex justify-start">
        <div className="max-w-[85%] rounded-md border border-gray-200 bg-gray-50 px-3 py-2 font-mono text-xs text-gray-700">
          <pre className="max-h-40 overflow-auto whitespace-pre-wrap">
            {message.content}
          </pre>
        </div>
      </div>
    );
  }

  // Assistant message
  const isStreamingEmpty = message.isStreaming && !message.content;
  const hasToolCalls = message.toolCalls && message.toolCalls.length > 0;
  const hasToolResults = message.toolResults && message.toolResults.length > 0;

  return (
    <div className="flex justify-start">
      <div className="max-w-[85%] rounded-2xl rounded-bl-md border border-gray-200 bg-white px-4 py-2.5 shadow-sm">
        {hasToolCalls && (
          <div className="mb-2 flex flex-wrap gap-1">
            {message.toolCalls!.map((tc, i) => (
              <ToolCallBadge key={i} name={tc.name} args={tc.args} />
            ))}
          </div>
        )}

        {hasToolResults && (
          <div className="mb-2 space-y-1">
            {message.toolResults!.map((tr, i) => (
              <ToolResultDisplay key={i} name={tr.name} result={tr.result} />
            ))}
          </div>
        )}

        {isStreamingEmpty ? (
          <TypingDots />
        ) : (
          <p className="whitespace-pre-wrap text-sm text-gray-800">
            {message.content}
            {message.isStreaming && <StreamingCursor />}
          </p>
        )}
      </div>
    </div>
  );
}
