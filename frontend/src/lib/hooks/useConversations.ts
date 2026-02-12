"use client";

import { useState, useCallback } from "react";
import { apiFetch } from "@/lib/api";

export interface Conversation {
  id: string;
  title: string | null;
  created_at: string;
  updated_at: string;
  message_count: number;
}

interface UseConversationsReturn {
  conversations: Conversation[];
  loading: boolean;
  error: string | null;
  fetchConversations: () => Promise<void>;
  deleteConversation: (id: string) => Promise<void>;
}

export function useConversations(): UseConversationsReturn {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchConversations = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiFetch<Conversation[]>(
        "/api/v1/chat/conversations",
      );
      setConversations(data);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to load conversations",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  const deleteConversation = useCallback(async (id: string) => {
    // Optimistic delete
    setConversations((prev) => prev.filter((c) => c.id !== id));
    try {
      await apiFetch(`/api/v1/chat/conversations/${id}`, {
        method: "DELETE",
      });
    } catch (err) {
      // Restore on failure — refetch the list
      setError(
        err instanceof Error ? err.message : "Failed to delete conversation",
      );
      try {
        const data = await apiFetch<Conversation[]>(
          "/api/v1/chat/conversations",
        );
        setConversations(data);
      } catch {
        // Ignore refetch error
      }
    }
  }, []);

  return {
    conversations,
    loading,
    error,
    fetchConversations,
    deleteConversation,
  };
}
