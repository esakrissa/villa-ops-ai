"use client";

import { useState, useCallback, useRef } from "react";
import { API_BASE_URL, apiFetch } from "@/lib/api";

// Tools that require HITL confirmation before execution
const DESTRUCTIVE_TOOLS = new Set(["property_delete", "guest_delete"]);

// ---- Types ----
export interface ConfirmationPayload {
  type: string;
  tool_name: string;
  args: Record<string, unknown>;
  message: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "tool";
  content: string;
  toolCalls?: { name: string; args: Record<string, unknown> }[];
  toolResults?: { name: string; result: string }[];
  isStreaming?: boolean;
  confirmation?: ConfirmationPayload;
  confirmationResolved?: boolean;
  confirmationAction?: "approve" | "cancel";
}

interface ConversationDetail {
  id: string;
  title: string;
  messages: {
    id: string;
    role: string;
    content: string;
    tool_calls: { name: string; args: Record<string, unknown> }[] | null;
    tool_results: { name: string; result: string }[] | null;
    model_used: string | null;
    created_at: string;
  }[];
}

interface UseChatReturn {
  messages: ChatMessage[];
  isLoading: boolean;
  error: string | null;
  conversationId: string | null;
  sendMessage: (message: string) => Promise<void>;
  resumeConversation: (action: "approve" | "cancel") => Promise<void>;
  clearMessages: () => void;
  setConversationId: (id: string | null) => void;
  loadConversation: (id: string) => Promise<void>;
}

let messageCounter = 0;
function generateId(): string {
  return `msg_${Date.now()}_${++messageCounter}`;
}

export function useChat(): UseChatReturn {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const sendMessage = useCallback(
    async (message: string) => {
      // Cancel any in-flight stream
      abortRef.current?.abort();
      abortRef.current = new AbortController();

      setError(null);
      setIsLoading(true);

      // Add user message immediately (optimistic)
      const userMessage: ChatMessage = {
        id: generateId(),
        role: "user",
        content: message,
      };

      // Add empty assistant placeholder with streaming flag
      const assistantId = generateId();
      const assistantMessage: ChatMessage = {
        id: assistantId,
        role: "assistant",
        content: "",
        toolCalls: [],
        toolResults: [],
        isStreaming: true,
      };

      setMessages((prev) => [...prev, userMessage, assistantMessage]);

      try {
        const token =
          typeof window !== "undefined"
            ? localStorage.getItem("access_token")
            : null;

        const response = await fetch(`${API_BASE_URL}/api/v1/chat`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: JSON.stringify({
            message,
            conversation_id: conversationId,
          }),
          signal: abortRef.current.signal,
        });

        if (!response.ok) {
          if (response.status === 401) {
            // Try token refresh
            try {
              const { refreshTokens } = await import("@/lib/auth");
              await refreshTokens();
              // Retry — remove the optimistic messages and re-send
              setMessages((prev) =>
                prev.filter(
                  (m) => m.id !== userMessage.id && m.id !== assistantId,
                ),
              );
              setIsLoading(false);
              // Re-invoke after refresh
              abortRef.current = new AbortController();
              return sendMessage(message);
            } catch {
              const { clearTokens } = await import("@/lib/auth");
              clearTokens();
              if (typeof window !== "undefined") {
                window.location.href = "/login";
              }
              throw new Error("Session expired");
            }
          }
          if (response.status === 402) {
            throw new Error(
              "You've reached your plan limit. Please upgrade to continue.",
            );
          }
          const data = await response.json().catch(() => ({}));
          throw new Error(
            typeof data?.detail === "string"
              ? data.detail
              : `Chat request failed: ${response.status}`,
          );
        }

        // Read SSE stream
        const reader = response.body!.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() || "";

          for (const line of lines) {
            const trimmedLine = line.trim();
            if (trimmedLine.startsWith("data:")) {
              const jsonStr = trimmedLine.slice(5).trim();
              if (!jsonStr || jsonStr === "[DONE]") continue;
              try {
                const event = JSON.parse(jsonStr);
                switch (event.type) {
                  case "token":
                    setMessages((prev) => {
                      const updated = [...prev];
                      const last = updated[updated.length - 1];
                      if (last && last.role === "assistant") {
                        updated[updated.length - 1] = {
                          ...last,
                          content: last.content + event.content,
                        };
                      }
                      return updated;
                    });
                    break;

                  case "tool_call":
                    setMessages((prev) => {
                      const updated = [...prev];
                      const last = updated[updated.length - 1];
                      if (last && last.role === "assistant") {
                        // Deduplicate: skip if same tool call already exists
                        const existing = last.toolCalls || [];
                        const isDupe = existing.some(
                          (tc) =>
                            tc.name === event.name &&
                            JSON.stringify(tc.args) ===
                              JSON.stringify(event.args),
                        );
                        if (!isDupe) {
                          updated[updated.length - 1] = {
                            ...last,
                            toolCalls: [
                              ...existing,
                              { name: event.name, args: event.args },
                            ],
                          };
                        }
                      }
                      return updated;
                    });
                    break;

                  case "tool_result":
                    setMessages((prev) => {
                      const updated = [...prev];
                      const last = updated[updated.length - 1];
                      if (last && last.role === "assistant") {
                        updated[updated.length - 1] = {
                          ...last,
                          toolResults: [
                            ...(last.toolResults || []),
                            { name: event.name, result: event.result },
                          ],
                        };
                      }
                      return updated;
                    });
                    break;

                  case "done":
                    setConversationId(event.conversation_id);
                    setMessages((prev) => {
                      const updated = [...prev];
                      const last = updated[updated.length - 1];
                      if (last && last.role === "assistant") {
                        updated[updated.length - 1] = {
                          ...last,
                          isStreaming: false,
                        };
                      }
                      return updated;
                    });
                    break;

                  case "confirmation":
                    setMessages((prev) => {
                      const updated = [...prev];
                      const last = updated[updated.length - 1];
                      if (last && last.role === "assistant") {
                        updated[updated.length - 1] = {
                          ...last,
                          confirmation: event.payload,
                          isStreaming: false,
                        };
                      }
                      return updated;
                    });
                    break;

                  case "interrupted":
                    setConversationId(event.conversation_id);
                    setMessages((prev) => {
                      const updated = [...prev];
                      const last = updated[updated.length - 1];
                      if (last && last.role === "assistant") {
                        updated[updated.length - 1] = {
                          ...last,
                          isStreaming: false,
                        };
                      }
                      return updated;
                    });
                    break;

                  case "error":
                    setError(event.message);
                    break;
                }
              } catch {
                // Skip malformed JSON
              }
            }
          }
        }
      } catch (err) {
        if ((err as Error).name === "AbortError") {
          // Request was cancelled, no action needed
          return;
        }
        setError(
          err instanceof Error ? err.message : "An unexpected error occurred",
        );
        // Remove the empty streaming assistant message on error
        setMessages((prev) => {
          const last = prev[prev.length - 1];
          if (last && last.role === "assistant" && !last.content) {
            return prev.slice(0, -1);
          }
          // Mark as not streaming if it had content
          if (last && last.role === "assistant" && last.isStreaming) {
            const updated = [...prev];
            updated[updated.length - 1] = { ...last, isStreaming: false };
            return updated;
          }
          return prev;
        });
      } finally {
        setIsLoading(false);
      }
    },
    [conversationId],
  );

  const resumeConversation = useCallback(
    async (action: "approve" | "cancel") => {
      if (!conversationId) return;

      // Mark the confirmation as resolved in the UI
      setMessages((prev) => {
        const updated = [...prev];
        const idx = updated.findLastIndex((m) => m.confirmation);
        if (idx !== -1) {
          updated[idx] = {
            ...updated[idx],
            confirmationResolved: true,
            confirmationAction: action,
          };
        }
        return updated;
      });

      // Cancel any in-flight stream
      abortRef.current?.abort();
      abortRef.current = new AbortController();

      setError(null);
      setIsLoading(true);

      // Add empty assistant placeholder for the resumed response
      const assistantId = generateId();
      const assistantMessage: ChatMessage = {
        id: assistantId,
        role: "assistant",
        content: "",
        toolCalls: [],
        toolResults: [],
        isStreaming: true,
      };
      setMessages((prev) => [...prev, assistantMessage]);

      try {
        const token =
          typeof window !== "undefined"
            ? localStorage.getItem("access_token")
            : null;

        const response = await fetch(
          `${API_BASE_URL}/api/v1/chat/${conversationId}/resume`,
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              ...(token ? { Authorization: `Bearer ${token}` } : {}),
            },
            body: JSON.stringify({ action }),
            signal: abortRef.current.signal,
          },
        );

        if (!response.ok) {
          const data = await response.json().catch(() => ({}));
          throw new Error(
            typeof data?.detail === "string"
              ? data.detail
              : `Resume failed: ${response.status}`,
          );
        }

        // Read SSE stream (same parsing as sendMessage)
        const reader = response.body!.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() || "";

          for (const line of lines) {
            const trimmedLine = line.trim();
            if (trimmedLine.startsWith("data:")) {
              const jsonStr = trimmedLine.slice(5).trim();
              if (!jsonStr || jsonStr === "[DONE]") continue;
              try {
                const event = JSON.parse(jsonStr);
                switch (event.type) {
                  case "token":
                    setMessages((prev) => {
                      const updated = [...prev];
                      const last = updated[updated.length - 1];
                      if (last && last.role === "assistant") {
                        updated[updated.length - 1] = {
                          ...last,
                          content: last.content + event.content,
                        };
                      }
                      return updated;
                    });
                    break;

                  case "tool_call":
                    setMessages((prev) => {
                      const updated = [...prev];
                      const last = updated[updated.length - 1];
                      if (last && last.role === "assistant") {
                        const existing = last.toolCalls || [];
                        const isDupe = existing.some(
                          (tc) =>
                            tc.name === event.name &&
                            JSON.stringify(tc.args) ===
                              JSON.stringify(event.args),
                        );
                        if (!isDupe) {
                          updated[updated.length - 1] = {
                            ...last,
                            toolCalls: [
                              ...existing,
                              { name: event.name, args: event.args },
                            ],
                          };
                        }
                      }
                      return updated;
                    });
                    break;

                  case "tool_result":
                    setMessages((prev) => {
                      const updated = [...prev];
                      const last = updated[updated.length - 1];
                      if (last && last.role === "assistant") {
                        updated[updated.length - 1] = {
                          ...last,
                          toolResults: [
                            ...(last.toolResults || []),
                            { name: event.name, result: event.result },
                          ],
                        };
                      }
                      return updated;
                    });
                    break;

                  case "done":
                    setMessages((prev) => {
                      const updated = [...prev];
                      const last = updated[updated.length - 1];
                      if (last && last.role === "assistant") {
                        updated[updated.length - 1] = {
                          ...last,
                          isStreaming: false,
                        };
                      }
                      return updated;
                    });
                    break;

                  case "error":
                    setError(event.message);
                    break;
                }
              } catch {
                // Skip malformed JSON
              }
            }
          }
        }
      } catch (err) {
        if ((err as Error).name === "AbortError") return;
        setError(
          err instanceof Error ? err.message : "An unexpected error occurred",
        );
        // Remove empty streaming assistant message on error
        setMessages((prev) => {
          const last = prev[prev.length - 1];
          if (last && last.role === "assistant" && !last.content) {
            return prev.slice(0, -1);
          }
          if (last && last.role === "assistant" && last.isStreaming) {
            const updated = [...prev];
            updated[updated.length - 1] = { ...last, isStreaming: false };
            return updated;
          }
          return prev;
        });
      } finally {
        setIsLoading(false);
      }
    },
    [conversationId],
  );

  const loadConversation = useCallback(async (id: string) => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await apiFetch<ConversationDetail>(
        `/api/v1/chat/conversations/${id}`,
      );
      // Merge tool messages into preceding assistant message's toolResults
      // Backend stores them as separate rows, but the UI expects them combined
      const loaded: ChatMessage[] = [];
      for (const m of data.messages) {
        if (m.role === "tool") {
          // Find the last assistant message and append this as a tool result
          for (let i = loaded.length - 1; i >= 0; i--) {
            if (loaded[i].role === "assistant" && loaded[i].toolCalls?.length) {
              const resultIndex = loaded[i].toolResults?.length ?? 0;
              const toolCall = loaded[i].toolCalls![resultIndex];
              loaded[i] = {
                ...loaded[i],
                toolResults: [
                  ...(loaded[i].toolResults ?? []),
                  { name: toolCall?.name ?? "tool", result: m.content },
                ],
              };
              break;
            }
          }
          continue;
        }
        loaded.push({
          id: m.id,
          role: m.role as ChatMessage["role"],
          content: m.content,
          toolCalls: m.tool_calls || undefined,
          toolResults: undefined,
        });
      }

      // Reconstruct HITL confirmation cards from DB data.
      // The confirmation/resolved state is ephemeral UI state not stored in DB,
      // so we rebuild it by detecting destructive tool calls in messages.
      for (let i = 0; i < loaded.length; i++) {
        const msg = loaded[i];
        if (msg.role !== "assistant" || !msg.toolCalls?.length) continue;

        const destructiveCall = msg.toolCalls.find((tc) =>
          DESTRUCTIVE_TOOLS.has(tc.name),
        );
        if (!destructiveCall) continue;

        const matchingResult = msg.toolResults?.find(
          (tr) => tr.name === destructiveCall.name,
        );

        if (matchingResult) {
          // Completed HITL flow — determine action from result content
          const wasCancelled = matchingResult.result
            .toLowerCase()
            .includes("cancelled");
          loaded[i] = {
            ...msg,
            confirmation: {
              type: "destructive_action",
              tool_name: destructiveCall.name,
              args: destructiveCall.args,
              message: `Are you sure you want to ${destructiveCall.name.replace(/_/g, " ")}?`,
            },
            confirmationResolved: true,
            confirmationAction: wasCancelled ? "cancel" : "approve",
          };
        } else if (i === loaded.length - 1) {
          // Interrupted (pending) — only for the last message
          loaded[i] = {
            ...msg,
            confirmation: {
              type: "destructive_action",
              tool_name: destructiveCall.name,
              args: destructiveCall.args,
              message: `Are you sure you want to ${destructiveCall.name.replace(/_/g, " ")}?`,
            },
          };
        }
      }

      setMessages(loaded);
      setConversationId(id);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to load conversation",
      );
    } finally {
      setIsLoading(false);
    }
  }, []);

  const clearMessages = useCallback(() => {
    abortRef.current?.abort();
    setMessages([]);
    setConversationId(null);
    setError(null);
  }, []);

  return {
    messages,
    isLoading,
    error,
    conversationId,
    sendMessage,
    resumeConversation,
    clearMessages,
    setConversationId,
    loadConversation,
  };
}
