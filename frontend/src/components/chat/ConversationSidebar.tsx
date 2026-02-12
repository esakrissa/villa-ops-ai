"use client";

import { useEffect } from "react";
import type { Conversation } from "@/lib/hooks/useConversations";

interface ConversationSidebarProps {
  isOpen: boolean;
  onClose: () => void;
  activeConversationId: string | null;
  onSelectConversation: (id: string) => void;
  onNewChat: () => void;
  conversations: Conversation[];
  loading: boolean;
  error: string | null;
  onDelete: (id: string) => void;
  onRefresh: () => void;
}

function formatRelativeTime(dateString: string): string {
  const now = new Date();
  const date = new Date(dateString);
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return "Just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  return date.toLocaleDateString();
}

export function ConversationSidebar({
  isOpen,
  onClose,
  activeConversationId,
  onSelectConversation,
  onNewChat,
  conversations,
  loading,
  error,
  onDelete,
  onRefresh,
}: ConversationSidebarProps) {
  // Fetch conversations when sidebar opens
  useEffect(() => {
    if (isOpen) {
      onRefresh();
    }
  }, [isOpen, onRefresh]);

  return (
    <>
      {/* Mobile backdrop */}
      {isOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/30 lg:hidden"
          onClick={onClose}
        />
      )}

      {/* Sidebar panel */}
      <aside
        className={`
          z-40 flex h-full w-80 shrink-0 flex-col border-r border-gray-200 bg-white
          transition-[transform] duration-200 ease-out
          max-lg:fixed max-lg:inset-y-0 max-lg:left-0
          ${isOpen ? "translate-x-0" : "-translate-x-full"}
        `}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-gray-200 px-4 py-3">
          <h2 className="text-sm font-semibold text-gray-900">Conversations</h2>
          <div className="flex items-center gap-1">
            <button
              onClick={() => {
                onNewChat();
                // Only close sidebar on mobile
                if (window.innerWidth < 1024) onClose();
              }}
              className="rounded-md p-1.5 text-gray-500 transition-colors hover:bg-gray-100 hover:text-gray-700"
              title="New chat"
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
                  d="m16.862 4.487 1.687-1.688a1.875 1.875 0 1 1 2.652 2.652L10.582 16.07a4.5 4.5 0 0 1-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 0 1 1.13-1.897l8.932-8.931Zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0 1 15.75 21H5.25A2.25 2.25 0 0 1 3 18.75V8.25A2.25 2.25 0 0 1 5.25 6H10"
                />
              </svg>
            </button>
            <button
              onClick={onClose}
              className="rounded-md p-1.5 text-gray-500 transition-colors hover:bg-gray-100 hover:text-gray-700 lg:hidden"
              title="Close"
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
        </div>

        {/* Conversation list */}
        <div className="flex-1 overflow-y-auto">
          {error ? (
            <div className="px-4 py-4 text-center text-sm text-red-500">
              <p>{error}</p>
              <button
                onClick={onRefresh}
                className="mt-2 text-indigo-600 hover:text-indigo-800"
              >
                Retry
              </button>
            </div>
          ) : loading && conversations.length === 0 ? (
            <div className="flex items-center justify-center py-8">
              <svg
                className="h-5 w-5 animate-spin text-gray-400"
                viewBox="0 0 24 24"
                fill="none"
              >
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
            </div>
          ) : conversations.length === 0 ? (
            <div className="px-4 py-8 text-center text-sm text-gray-500">
              No conversations yet
            </div>
          ) : (
            <ul className="py-1">
              {conversations.map((conv) => {
                const isActive = conv.id === activeConversationId;
                return (
                  <li key={conv.id} className="group relative">
                    <button
                      onClick={() => {
                        onSelectConversation(conv.id);
                        if (window.innerWidth < 1024) onClose();
                      }}
                      className={`flex w-full flex-col gap-0.5 px-4 py-2.5 text-left transition-colors ${
                        isActive
                          ? "bg-indigo-50 text-indigo-700"
                          : "text-gray-700 hover:bg-gray-50"
                      }`}
                    >
                      <span
                        className={`truncate text-sm font-medium ${
                          isActive ? "text-indigo-700" : "text-gray-900"
                        }`}
                      >
                        {conv.title || "Untitled"}
                      </span>
                      <span className="flex items-center gap-2 text-xs text-gray-500">
                        <span>{formatRelativeTime(conv.updated_at)}</span>
                        <span className="inline-flex items-center rounded-full bg-gray-100 px-1.5 py-0.5 text-xs text-gray-600">
                          {conv.message_count}
                        </span>
                      </span>
                    </button>
                    {/* Delete button */}
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onDelete(conv.id);
                      }}
                      className="absolute right-2 top-1/2 -translate-y-1/2 rounded-md p-1 text-gray-400 opacity-0 transition-opacity hover:bg-red-50 hover:text-red-500 group-hover:opacity-100 max-lg:opacity-100"
                      title="Delete conversation"
                    >
                      <svg
                        className="h-4 w-4"
                        fill="none"
                        viewBox="0 0 24 24"
                        strokeWidth={1.5}
                        stroke="currentColor"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          d="m14.74 9-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 0 1-2.244 2.077H8.084a2.25 2.25 0 0 1-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 0 0-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 0 1 3.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 0 0-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 0 0-7.5 0"
                        />
                      </svg>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </aside>
    </>
  );
}
