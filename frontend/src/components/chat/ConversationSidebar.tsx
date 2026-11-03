"use client";

import { useEffect, useMemo, useState } from "react";
import type { Conversation } from "@/lib/hooks/useConversations";
import { parseApiDate } from "@/lib/date";
import { ChatsIcon, CloseIcon, PenIcon, SearchIcon, TrashIcon } from "@/components/ui/icons";

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

const GROUPS = ["Today", "Yesterday", "Previous 7 days", "Older"] as const;

function groupFor(dateString: string): (typeof GROUPS)[number] {
  const date = parseApiDate(dateString);
  const startOfToday = new Date();
  startOfToday.setHours(0, 0, 0, 0);
  const dayMs = 86400000;
  if (date >= startOfToday) return "Today";
  if (date.getTime() >= startOfToday.getTime() - dayMs) return "Yesterday";
  if (date.getTime() >= startOfToday.getTime() - 7 * dayMs) return "Previous 7 days";
  return "Older";
}

function isMobile() {
  return typeof window !== "undefined" && window.innerWidth < 1024;
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
  const [query, setQuery] = useState("");

  useEffect(() => {
    if (isOpen) onRefresh();
  }, [isOpen, onRefresh]);

  const grouped = useMemo(() => {
    const q = query.trim().toLowerCase();
    const filtered = q ? conversations.filter((c) => (c.title || "").toLowerCase().includes(q)) : conversations;
    const map = new Map<string, Conversation[]>();
    for (const c of filtered) {
      const g = groupFor(c.updated_at);
      map.set(g, [...(map.get(g) || []), c]);
    }
    return GROUPS.filter((g) => map.has(g)).map((g) => [g, map.get(g)!] as const);
  }, [conversations, query]);

  return (
    <>
      {isOpen && <div className="fixed inset-0 z-30 bg-coal/25 backdrop-blur-[2px] lg:hidden" onClick={onClose} />}

      <aside
        aria-hidden={!isOpen}
        className={`z-40 flex h-full shrink-0 flex-col overflow-hidden border-r border-gray-200/70 bg-gray-50 transition-[width,transform] duration-200 ease-out max-lg:fixed max-lg:inset-y-0 max-lg:left-0 max-lg:w-80 ${
          isOpen ? "max-lg:translate-x-0 lg:w-72" : "max-lg:-translate-x-full lg:w-0 lg:border-r-0"
        }`}
      >
        <div className="flex w-80 flex-col lg:w-72">
          <div className="flex h-14 items-center justify-between px-3">
            <button
              type="button"
              onClick={onClose}
              title="Collapse history"
              aria-label="Collapse history"
              className="rounded-lg p-1.5 text-gray-500 transition-colors hover:bg-gray-100 hover:text-ink"
            >
              <span className="lg:hidden">
                <CloseIcon className="h-4 w-4" />
              </span>
              <span className="hidden lg:block">
                <ChatsIcon />
              </span>
            </button>
            <p className="eyebrow text-gray-500">History</p>
            <button
              type="button"
              onClick={() => {
                onNewChat();
                if (isMobile()) onClose();
              }}
              title="New chat"
              aria-label="New chat"
              className="rounded-lg p-1.5 text-gray-500 transition-colors hover:bg-gray-100 hover:text-ink"
            >
              <PenIcon />
            </button>
          </div>

          <div className="px-3 pb-2">
            <label className="flex items-center gap-2 rounded-xl border border-gray-200 bg-white px-3 py-2 text-gray-400 focus-within:border-gray-300">
              <SearchIcon className="h-4 w-4" />
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search chats"
                className="w-full bg-transparent text-[13px] text-ink outline-none placeholder:text-gray-400"
              />
            </label>
          </div>
        </div>

        <div className="min-h-0 w-80 flex-1 overflow-y-auto px-2 pb-4 lg:w-72">
          {error ? (
            <div className="px-3 py-6 text-center text-[13px] text-red-600">
              <p>{error}</p>
              <button type="button" onClick={onRefresh} className="mt-2 font-medium text-ink underline">
                Retry
              </button>
            </div>
          ) : loading && conversations.length === 0 ? (
            <div className="space-y-2 px-2 pt-3">
              {[0, 1, 2, 3].map((i) => (
                <div key={i} className="h-8 animate-pulse rounded-lg bg-gray-100" />
              ))}
            </div>
          ) : grouped.length === 0 ? (
            <p className="px-3 py-8 text-center text-[13px] text-gray-500">
              {query ? "No chats match your search" : "No conversations yet"}
            </p>
          ) : (
            grouped.map(([group, items]) => (
              <div key={group} className="mt-3 first:mt-1">
                <p className="eyebrow mb-1 px-3 !text-[10px] text-gray-400">{group}</p>
                <ul>
                  {items.map((conv) => {
                    const active = conv.id === activeConversationId;
                    return (
                      <li key={conv.id} className="group relative">
                        <button
                          type="button"
                          onClick={() => {
                            onSelectConversation(conv.id);
                            if (isMobile()) onClose();
                          }}
                          className={`flex w-full items-center rounded-lg py-2 pl-3 pr-9 text-left text-[13.5px] transition-colors ${
                            active ? "bg-sand font-medium text-ink" : "text-gray-700 hover:bg-gray-100"
                          }`}
                        >
                          <span className="truncate">{conv.title || "Untitled"}</span>
                        </button>
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            onDelete(conv.id);
                          }}
                          title="Delete conversation"
                          className="absolute right-1.5 top-1/2 -translate-y-1/2 rounded-md p-1 text-gray-400 opacity-0 transition-opacity hover:bg-white hover:text-red-600 group-hover:opacity-100 max-lg:opacity-100"
                        >
                          <TrashIcon className="h-3.5 w-3.5" />
                        </button>
                      </li>
                    );
                  })}
                </ul>
              </div>
            ))
          )}
        </div>
      </aside>
    </>
  );
}
