"use client";

import { useState } from "react";
import { ChatWindow } from "@/components/chat/ChatWindow";
import { ChatInput } from "@/components/chat/ChatInput";
import { useChat } from "@/lib/hooks/useChat";

export default function ChatPage() {
  const { messages, isLoading, error, sendMessage } = useChat();
  const [showError, setShowError] = useState(true);

  return (
    <div className="-m-6 flex h-[calc(100%+3rem)] flex-col">
      {/* Error banner */}
      {error && showError && (
        <div className="flex items-center justify-between border-b border-red-200 bg-red-50 px-4 py-2 text-sm text-red-700">
          <span>{error}</span>
          <button
            onClick={() => setShowError(false)}
            className="ml-4 text-red-500 hover:text-red-700"
          >
            <svg
              className="h-4 w-4"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth={2}
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M6 18 18 6M6 6l12 12"
              />
            </svg>
          </button>
        </div>
      )}

      {/* Message list */}
      <div className="flex-1 overflow-hidden bg-gray-50">
        <ChatWindow
          messages={messages}
          isLoading={isLoading}
          onSuggestionClick={sendMessage}
        />
      </div>

      {/* Input area */}
      <div className="border-t border-gray-200 bg-white px-4 py-4">
        <ChatInput onSend={sendMessage} disabled={isLoading} />
      </div>
    </div>
  );
}
