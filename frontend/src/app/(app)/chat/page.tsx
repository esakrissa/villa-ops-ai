"use client";

import { useState, useCallback, useEffect, useRef, useSyncExternalStore } from "react";
import { ChatWindow } from "@/components/chat/ChatWindow";
import { ChatInput } from "@/components/chat/ChatInput";
import { ConversationSidebar } from "@/components/chat/ConversationSidebar";
import { PromptTemplates } from "@/components/chat/PromptTemplates";
import { VoiceMode } from "@/components/voice/VoiceMode";
import { ConfirmModal } from "@/components/ui/ConfirmModal";
import { ChatsIcon, CloseIcon, PenIcon, WaveIcon } from "@/components/ui/icons";
import { useAuth } from "@/lib/hooks/useAuth";
import { useChat } from "@/lib/hooks/useChat";
import { useConversations } from "@/lib/hooks/useConversations";
import { useMediaQuery, usePersistentState } from "@/lib/hooks/usePersistentState";
import { useVoiceConfig } from "@/lib/hooks/useVoiceSession";

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
    generatedTitle,
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
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null);
  const prevConvIdRef = useRef<string | null>(null);
  const [templatesOpen, setTemplatesOpen] = usePersistentState("villaops.templates.open", true);
  const voiceConfig = useVoiceConfig();
  const [voiceOpen, setVoiceOpen] = useState(false);
  const voiceAvailable = !!voiceConfig?.enabled;
  const openVoice = useCallback(() => {
    stopGeneration();
    setVoiceOpen(true);
  }, [stopGeneration]);
  const toggleTemplates = useCallback(() => setTemplatesOpen(!templatesOpen), [setTemplatesOpen, templatesOpen]);

  // The call is saved as a conversation: show it as a chat when the call ends
  const handleVoiceExit = useCallback(
    (convId: string | null, hadTurns: boolean) => {
      setVoiceOpen(false);
      if (convId && (hadTurns || convId === conversationId)) loadConversation(convId);
      fetchConversations();
      // The LLM title arrives a few seconds after the first question
      setTimeout(fetchConversations, 4000);
    },
    [conversationId, fetchConversations, loadConversation],
  );

  // Refresh history when a new conversation is created
  useEffect(() => {
    if (conversationId && prevConvIdRef.current !== conversationId && !isLoading) {
      fetchConversations();
    }
    prevConvIdRef.current = conversationId;
  }, [conversationId, isLoading, fetchConversations]);

  const handleSelectConversation = useCallback(
    (id: string) => {
      if (voiceOpen) return;
      if (id !== conversationId) loadConversation(id);
    },
    [conversationId, loadConversation, voiceOpen],
  );

  // Refresh history when the LLM-generated title arrives
  useEffect(() => {
    if (generatedTitle) fetchConversations();
  }, [generatedTitle, fetchConversations]);

  const confirmDelete = useCallback(() => {
    const id = pendingDeleteId;
    setPendingDeleteId(null);
    if (!id) return;
    deleteConversation(id);
    if (id === conversationId) clearMessages();
  }, [pendingDeleteId, deleteConversation, conversationId, clearMessages]);

  const isEmpty = messages.length === 0 && !isLoading;
  const title = generatedTitle ?? conversations.find((c) => c.id === conversationId)?.title;
  const pendingDeleteTitle = conversations.find((c) => c.id === pendingDeleteId)?.title;
  const firstName = user?.name?.split(" ")[0];
  const hello = useGreeting();

  return (
    <div className="flex h-full">
      <ConfirmModal
        open={!!pendingDeleteId}
        title="Delete conversation?"
        description={`"${pendingDeleteTitle || "Untitled"}" and all its messages will be permanently deleted. This can't be undone.`}
        confirmLabel="Delete"
        cancelLabel="Keep it"
        destructive
        onConfirm={confirmDelete}
        onCancel={() => setPendingDeleteId(null)}
      />
      <ConversationSidebar
        isOpen={historyOpen}
        onClose={() => setHistoryOpen(false)}
        activeConversationId={conversationId}
        onSelectConversation={handleSelectConversation}
        onNewChat={clearMessages}
        conversations={conversations}
        loading={convsLoading}
        error={convsError}
        onDelete={setPendingDeleteId}
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
            {voiceOpen ? (
              <span className="inline-flex items-center gap-1.5 text-ink">
                <WaveIcon className="h-4 w-4" /> Voice call with Villa
                {!isEmpty && title ? <span className="text-gray-400">· {title}</span> : null}
              </span>
            ) : isEmpty ? (
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

        {voiceOpen ? (
          <VoiceMode conversationId={isEmpty ? null : conversationId} onExit={handleVoiceExit} />
        ) : isEmpty ? (
          /* Welcome: greeting + centred composer + prompt templates */
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
                <ChatInput
                  onSend={sendMessage}
                  isLoading={isLoading}
                  onStop={stopGeneration}
                  autoFocus
                  onVoice={voiceAvailable ? openVoice : undefined}
                  templatesOpen={templatesOpen}
                  onToggleTemplates={toggleTemplates}
                />
              </div>
              {voiceAvailable && (
                <p className="mt-3 text-center text-[13px] text-gray-500">
                  Prefer to talk?{" "}
                  <button type="button" onClick={openVoice} className="font-medium text-ink underline decoration-gray-300 underline-offset-2 hover:decoration-ink">
                    Call Villa
                  </button>
                  , the voice concierge: trip plans for Ubud, your bookings and policies, hands-free.
                </p>
              )}
              {templatesOpen && (
                <div className="mx-auto mt-6 max-w-3xl">
                  <PromptTemplates variant="text" onPick={sendMessage} />
                </div>
              )}
            </div>
          </div>
        ) : (
          <>
            <div className="min-h-0 flex-1 overflow-y-auto">
              <ChatWindow messages={messages} onResumeConversation={resumeConversation} />
            </div>
            <div className="relative shrink-0 px-4 pb-4">
              <div className="pointer-events-none absolute inset-x-0 -top-8 h-8 bg-gradient-to-t from-cream to-transparent" />
              {templatesOpen && (
                <div className="mx-auto mb-2 w-full max-w-3xl rounded-2xl border border-gray-200 bg-white/80 px-3 pb-3 pt-2 backdrop-blur">
                  <PromptTemplates variant="text" compact disabled={isLoading} onPick={sendMessage} />
                </div>
              )}
              <ChatInput
                onSend={sendMessage}
                isLoading={isLoading}
                onStop={stopGeneration}
                placeholder="Reply to VillaOps…"
                onVoice={voiceAvailable ? openVoice : undefined}
                templatesOpen={templatesOpen}
                onToggleTemplates={toggleTemplates}
              />
            </div>
          </>
        )}
      </div>
    </div>
  );
}
