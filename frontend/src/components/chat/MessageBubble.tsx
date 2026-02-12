"use client";

import type { ChatMessage } from "@/lib/hooks/useChat";
import { ToolCallCard } from "./ToolCallCard";

interface MessageBubbleProps {
  message: ChatMessage;
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

  return (
    <div className="flex justify-start">
      <div className="max-w-[85%] rounded-2xl rounded-bl-md border border-gray-200 bg-white px-4 py-2.5 shadow-sm">
        {hasToolCalls && (
          <div className="mb-2 space-y-2">
            {message.toolCalls!.map((tc, i) => (
              <ToolCallCard
                key={i}
                name={tc.name}
                args={tc.args}
                result={message.toolResults?.[i]?.result}
                isStreaming={message.isStreaming}
              />
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
