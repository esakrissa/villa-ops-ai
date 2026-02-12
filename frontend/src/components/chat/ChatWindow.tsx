"use client";

import { useEffect, useRef } from "react";
import { MessageBubble } from "./MessageBubble";
import type { ChatMessage } from "@/lib/hooks/useChat";

interface ChatWindowProps {
  messages: ChatMessage[];
  isLoading: boolean;
  onSuggestionClick?: (suggestion: string) => void;
}

const suggestions = [
  "Show me today's check-ins",
  "What's the occupancy rate this month?",
  "Search for guest Sarah Lee",
  "Create a booking for Villa Sunset",
];

function EmptyState({
  onSuggestionClick,
}: {
  onSuggestionClick?: (suggestion: string) => void;
}) {
  return (
    <div className="flex h-full flex-col items-center justify-center px-4">
      <div className="mb-6 flex h-16 w-16 items-center justify-center rounded-2xl bg-indigo-100">
        <svg
          className="h-8 w-8 text-indigo-600"
          fill="none"
          viewBox="0 0 24 24"
          strokeWidth={1.5}
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M8.625 12a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0H8.25m4.125 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0H12m4.125 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 0 1-2.555-.337A5.972 5.972 0 0 1 5.41 20.97a5.969 5.969 0 0 1-.474-.065 4.48 4.48 0 0 0 .978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25Z"
          />
        </svg>
      </div>
      <h2 className="text-xl font-semibold text-gray-900">VillaOps AI</h2>
      <p className="mt-2 max-w-sm text-center text-sm text-gray-500">
        Your AI-powered assistant for villa operations. Ask me anything about
        bookings, guests, properties, or analytics.
      </p>
      <div className="mt-6 flex flex-wrap justify-center gap-2">
        {suggestions.map((suggestion) => (
          <button
            key={suggestion}
            onClick={() => onSuggestionClick?.(suggestion)}
            className="rounded-full border border-gray-200 bg-white px-4 py-2 text-sm text-gray-700 shadow-sm transition-colors hover:border-indigo-300 hover:bg-indigo-50 hover:text-indigo-700"
          >
            {suggestion}
          </button>
        ))}
      </div>
    </div>
  );
}

export function ChatWindow({
  messages,
  isLoading,
  onSuggestionClick,
}: ChatWindowProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  if (messages.length === 0 && !isLoading) {
    return <EmptyState onSuggestionClick={onSuggestionClick} />;
  }

  return (
    <div className="flex h-full flex-col overflow-y-auto">
      <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-4 px-4 py-6">
        {messages.map((message) => (
          <MessageBubble key={message.id} message={message} />
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
