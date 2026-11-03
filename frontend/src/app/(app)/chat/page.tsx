"use client";

import { useState, useCallback, useEffect, useRef, useSyncExternalStore } from "react";
import { ChatWindow } from "@/components/chat/ChatWindow";
import { ChatInput } from "@/components/chat/ChatInput";
import { ConversationSidebar } from "@/components/chat/ConversationSidebar";
import { ChatsIcon, CloseIcon, PenIcon } from "@/components/ui/icons";
import { useAuth } from "@/lib/hooks/useAuth";
import { useChat } from "@/lib/hooks/useChat";
import { useConversations } from "@/lib/hooks/useConversations";
import { useMediaQuery, usePersistentState } from "@/lib/hooks/usePersistentState";

const suggestions = [
  { title: "Today's check-ins", prompt: "Show me today's check-ins" },
  { title: "Occupancy this month", prompt: "What's the occupancy rate this month?" },
  { title: "Find a guest", prompt: "Search for guest Sarah Chen" },
  { title: "Upcoming arrivals", prompt: "Which guests are arriving in the next 7 days?" },
];

function greeting(): string {
  const hour = new Date().getHours();
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}

const noopSubscribe = () => () => {};

/** Time-of-day greeting in the viewer's timezone (neutral on the server). */
function useGreeting(): string {
  return useSyncExternalStore(noopSubscribe, greeting, () => "Hello");
}

export default function ChatPage() {
  const { user } = useAuth();
  const {
    messages,
    isLoading,
    error,
    conversationId,
    sendMessage,
    resumeConversation,
    clearMessages,
    stopGeneration,
    loadConversation,
  } = useChat();
  const {
    conversations,
    loading: convsLoading,
    error: convsError,
    fetchConversations,
    deleteConversation,
  } = useConversations();

  // Desktop remembers the history panel; on mobile it's an overlay that starts closed
  const isDesktop = useMediaQuery("(min-width: 1024px)");
  const [desktopHistoryOpen, setDesktopHistoryOpen] = usePersistentState("villaops.history.open", true);
  const [mobileHistoryOpen, setMobileHistoryOpen] = useState(false);
  const historyOpen = isDesktop ? desktopHistoryOpen : mobileHistoryOpen;
  const setHistoryOpen = isDesktop ? setDesktopHistoryOpen : setMobileHistoryOpen;
  const [dismissedError, setDismissedError] = useState<string | null>(null);
  const prevConvIdRef = useRef<string | null>(null);

  // Refresh history when a new conversation is created
  useEffect(() => {
    if (conversationId && prevConvIdRef.current !== conversationId && !isLoading) {
      fetchConversations();
    }
    prevConvIdRef.current = conversationId;
  }, [conversationId, isLoading, fetchConversations]);

  const handleSelectConversation = useCallback(
    (id: string) => {
      if (id !== conversationId) loadConversation(id);
    },
    [conversationId, loadConversation],
  );

  const handleDelete = useCallback(
    (id: string) => {
      deleteConversation(id);
      if (id === conversationId) clearMessages();
    },
    [deleteConversation, conversationId, clearMessages],
  );

  const isEmpty = messages.length === 0 && !isLoading;
  const title = conversations.find((c) => c.id === conversationId)?.title;
  const firstName = user?.name?.split(" ")[0];
  const hello = useGreeting();

  return (
    <div className="flex h-full">
      <ConversationSidebar
        isOpen={historyOpen}
        onClose={() => setHistoryOpen(false)}
        activeConversationId={conversationId}
        onSelectConversation={handleSelectConversation}
        onNewChat={clearMessages}
        conversations={conversations}
        loading={convsLoading}
        error={convsError}
        onDelete={handleDelete}
        onRefresh={fetchConversations}
      />

      <div className="relative flex min-w-0 flex-1 flex-col bg-cream">
        {/* Top bar */}
        <div className="flex h-14 shrink-0 items-center gap-1 px-3">
          {!historyOpen && (
            <button
              type="button"
              onClick={() => setHistoryOpen(true)}
              title="Show history"
              aria-label="Show history"
              className="rounded-lg p-1.5 text-gray-500 transition-colors hover:bg-gray-100 hover:text-ink"
            >
              <ChatsIcon />
            </button>
          )}
          {!historyOpen && (
            <button
              type="button"
              onClick={clearMessages}
              title="New chat"
              aria-label="New chat"
              className="rounded-lg p-1.5 text-gray-500 transition-colors hover:bg-gray-100 hover:text-ink"
            >
              <PenIcon />
            </button>
          )}
          <p className="ml-2 min-w-0 truncate text-[14px] text-gray-600">
            {isEmpty ? (
              <span className="eyebrow text-gray-400">New conversation</span>
            ) : (
              title || "Conversation"
            )}
          </p>
        </div>

        {error && error !== dismissedError && (
          <div className="mx-auto mt-1 flex w-full max-w-3xl items-center justify-between gap-3 rounded-xl border border-red-200 bg-red-50 px-4 py-2.5 text-[13px] text-red-700">
            <span>{error}</span>
            <button type="button" onClick={() => setDismissedError(error)} className="text-red-400 hover:text-red-700">
              <CloseIcon className="h-4 w-4" />
            </button>
          </div>
        )}

        {isEmpty ? (
          /* Welcome: greeting + centred composer + suggestions */
          <div className="flex min-h-0 flex-1 flex-col overflow-y-auto px-4">
            <div className="mx-auto my-auto w-full max-w-3xl py-10">
              <p className="eyebrow text-center text-gray-500">VillaOps agent</p>
              <h1 className="display mt-4 text-center text-[44px] text-ink sm:text-[56px]">
                {hello}
                {firstName ? `, ${firstName}` : ""}.
                <br />
                <em>What needs doing?</em>
              </h1>
              <div className="mt-10">
                <ChatInput onSend={sendMessage} isLoading={isLoading} onStop={stopGeneration} autoFocus />
              </div>
              <div className="mx-auto mt-6 grid max-w-3xl grid-cols-1 gap-2 sm:grid-cols-2">
                {suggestions.map((s) => (
                  <button
                    key={s.prompt}
                    type="button"
                    onClick={() => sendMessage(s.prompt)}
                    className="group rounded-2xl border border-gray-200 bg-white/60 px-4 py-3 text-left transition-colors hover:border-gray-300 hover:bg-white"
                  >
                    <span className="block text-[14px] font-medium text-ink">{s.title}</span>
                    <span className="block truncate text-[13px] text-gray-500">{s.prompt}</span>
                  </button>
                ))}
              </div>
            </div>
          </div>
        ) : (
          <>
            <div className="min-h-0 flex-1 overflow-y-auto">
              <ChatWindow messages={messages} onResumeConversation={resumeConversation} />
            </div>
            <div className="relative shrink-0 px-4 pb-4">
              <div className="pointer-events-none absolute inset-x-0 -top-8 h-8 bg-gradient-to-t from-cream to-transparent" />
              <ChatInput onSend={sendMessage} isLoading={isLoading} onStop={stopGeneration} placeholder="Reply to VillaOps…" />
            </div>
          </>
        )}
      </div>
    </div>
  );
}
