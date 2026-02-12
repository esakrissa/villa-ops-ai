"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import { ChatWindow } from "@/components/chat/ChatWindow";
import { ChatInput } from "@/components/chat/ChatInput";
import { ConversationSidebar } from "@/components/chat/ConversationSidebar";
import { useChat } from "@/lib/hooks/useChat";
import { useConversations } from "@/lib/hooks/useConversations";

export default function ChatPage() {
  const {
    messages,
    isLoading,
    error,
    conversationId,
    sendMessage,
    clearMessages,
    loadConversation,
  } = useChat();
  const {
    conversations,
    loading: convsLoading,
    error: convsError,
    fetchConversations,
    deleteConversation,
  } = useConversations();

  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [showError, setShowError] = useState(true);
  const prevConvIdRef = useRef<string | null>(null);

  // Refresh sidebar when a new conversation is created (conversationId changes from null to a value)
  useEffect(() => {
    if (
      conversationId &&
      prevConvIdRef.current !== conversationId &&
      !isLoading
    ) {
      fetchConversations();
    }
    prevConvIdRef.current = conversationId;
  }, [conversationId, isLoading, fetchConversations]);

  // Reset showError when error changes
  useEffect(() => {
    if (error) setShowError(true);
  }, [error]);

  const handleSelectConversation = useCallback(
    (id: string) => {
      if (id !== conversationId) {
        loadConversation(id);
      }
    },
    [conversationId, loadConversation],
  );

  const handleNewChat = useCallback(() => {
    clearMessages();
  }, [clearMessages]);

  const handleDelete = useCallback(
    (id: string) => {
      deleteConversation(id);
      // If the deleted conversation was active, clear the chat
      if (id === conversationId) {
        clearMessages();
      }
    },
    [deleteConversation, conversationId, clearMessages],
  );

  return (
    <div className="-m-4 md:-m-6 flex h-[calc(100%+2rem)] md:h-[calc(100%+3rem)]">
      {/* Conversation sidebar */}
      <ConversationSidebar
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        activeConversationId={conversationId}
        onSelectConversation={handleSelectConversation}
        onNewChat={handleNewChat}
        conversations={conversations}
        loading={convsLoading}
        error={convsError}
        onDelete={handleDelete}
        onRefresh={fetchConversations}
      />

      {/* Main chat area */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Chat header */}
        <div className="flex items-center gap-2 border-b border-gray-200 bg-white px-4 py-2">
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="rounded-md p-1.5 text-gray-500 transition-colors hover:bg-gray-100 hover:text-gray-700"
            title="Conversation history"
          >
            <svg
              className="h-5 w-5"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth={1.5}
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M12 6v6h4.5m4.5 0a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z"
              />
            </svg>
          </button>
          <button
            onClick={handleNewChat}
            className="flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-sm text-gray-600 transition-colors hover:bg-gray-100 hover:text-gray-800"
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
                d="M12 4.5v15m7.5-7.5h-15"
              />
            </svg>
            New Chat
          </button>
        </div>

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
    </div>
  );
}
