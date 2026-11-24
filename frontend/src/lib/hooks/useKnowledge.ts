"use client";

import { useCallback, useEffect, useState } from "react";
import { API_BASE_URL, ApiError, apiFetch } from "@/lib/api";

export type DocStatus = "queued" | "extracting" | "chunking" | "indexing" | "verifying" | "ready" | "failed";

export const ACTIVE_STATUSES: DocStatus[] = ["queued", "extracting", "chunking", "indexing", "verifying"];

export interface KnowledgeDocument {
  id: string;
  name: string;
  file_type: string;
  size_bytes: number;
  status: DocStatus;
  error: string | null;
  page_count: number | null;
  char_count: number;
  token_count: number;
  chunk_count: number;
  indexed_count: number;
  embed_model: string | null;
  created_at: string;
  updated_at: string;
}

export interface KnowledgeChunk {
  id: string;
  position: number;
  text: string;
  heading: string | null;
  page: number | null;
  token_count: number;
  status: "pending" | "indexed";
  /** Index within the batch it arrived in — drives the staggered reveal */
  arrival?: number;
}

export interface KnowledgeStatus {
  enabled: boolean;
  index: string;
  embed_model: string;
  rerank_model: string | null;
  max_upload_mb: number;
  supported_types: string[];
  chunk_tokens: number;
  overlap_tokens: number;
}

export interface SearchResult {
  document: string;
  document_id: string;
  section: string | null;
  page: number | null;
  chunk: number;
  score: number;
  text: string;
}

export interface SearchResponse {
  query: string;
  results: SearchResult[];
  total: number;
  reranked: boolean;
  latency_ms: number;
}

/** fetch() with the bearer token and one refresh-on-401 retry (for multipart + SSE, which apiFetch can't do). */
async function authedFetch(path: string, init: RequestInit = {}, retry = true): Promise<Response> {
  const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : null;
  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: { ...(init.headers as Record<string, string>), ...(token ? { Authorization: `Bearer ${token}` } : {}) },
  });
  if (res.status === 401 && retry) {
    const { refreshTokens } = await import("@/lib/auth");
    await refreshTokens();
    return authedFetch(path, init, false);
  }
  return res;
}

export async function uploadDocument(file: File): Promise<KnowledgeDocument> {
  const form = new FormData();
  form.append("file", file);
  const res = await authedFetch("/api/v1/knowledge/documents", { method: "POST", body: form });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new ApiError(res.status, data);
  }
  return res.json();
}

export function deleteDocument(id: string): Promise<void> {
  return apiFetch<void>(`/api/v1/knowledge/documents/${id}`, { method: "DELETE" });
}

export function searchKnowledge(query: string, topK = 5): Promise<SearchResponse> {
  return apiFetch<SearchResponse>("/api/v1/knowledge/search", {
    method: "POST",
    body: JSON.stringify({ query, top_k: topK }),
  });
}

type StreamEvent =
  | { type: "document"; document: KnowledgeDocument }
  | { type: "chunks"; chunks: KnowledgeChunk[] }
  | { type: "indexed"; positions: number[] }
  | { type: "done"; status: string };

/** Read the ingestion SSE stream for one document until it finishes or `signal` aborts. */
export async function streamDocumentEvents(
  id: string,
  onEvent: (e: StreamEvent) => void,
  signal: AbortSignal,
): Promise<void> {
  const res = await authedFetch(`/api/v1/knowledge/documents/${id}/events`, { signal });
  if (!res.ok || !res.body) throw new Error(`Stream failed: ${res.status}`);
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";
    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed.startsWith("data:")) continue;
      const json = trimmed.slice(5).trim();
      if (!json) continue;
      try {
        onEvent(JSON.parse(json) as StreamEvent);
      } catch {
        /* ignore malformed line */
      }
    }
  }
}

export function useKnowledgeDocuments() {
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([]);
  const [status, setStatus] = useState<KnowledgeStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refetch = useCallback(async () => {
    try {
      const data = await apiFetch<{ items: KnowledgeDocument[] }>("/api/v1/knowledge/documents");
      setDocuments(data.items);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load documents");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refetch();
    apiFetch<KnowledgeStatus>("/api/v1/knowledge/status").then(setStatus).catch(() => setStatus(null));
  }, [refetch]);

  // Keep list counters fresh while any document is still processing
  const anyActive = documents.some((d) => ACTIVE_STATUSES.includes(d.status));
  useEffect(() => {
    if (!anyActive) return;
    const t = setInterval(() => void refetch(), 1500);
    return () => clearInterval(t);
  }, [anyActive, refetch]);

  const upsert = useCallback((doc: KnowledgeDocument) => {
    setDocuments((prev) => {
      const i = prev.findIndex((d) => d.id === doc.id);
      if (i === -1) return [doc, ...prev];
      const next = [...prev];
      next[i] = doc;
      return next;
    });
  }, []);

  const remove = useCallback((id: string) => setDocuments((prev) => prev.filter((d) => d.id !== id)), []);

  return { documents, status, loading, error, refetch, upsert, remove };
}
