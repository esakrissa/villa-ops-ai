"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { usePersistentState } from "./usePersistentState";

export interface AgentModel {
  id: string;
  label: string;
  default: boolean;
}

export const MODEL_KEY = "villaops.model";

/** Read the picked model synchronously — used when sending a message. */
export function readSelectedModel(): string | null {
  try {
    const raw = window.localStorage.getItem(MODEL_KEY);
    const parsed = raw ? JSON.parse(raw) : null;
    return typeof parsed === "string" && parsed ? parsed : null;
  } catch {
    return null;
  }
}

/** Chat models the user can pick, plus the per-browser choice (sent with each request). */
export function useAgentModels() {
  const [models, setModels] = useState<AgentModel[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedId, setSelectedId] = usePersistentState<string>(MODEL_KEY, "");

  useEffect(() => {
    apiFetch<AgentModel[]>("/api/v1/chat/models")
      .then(setModels)
      .catch(() => setModels([]))
      .finally(() => setLoading(false));
  }, []);

  // Fall back to the server default when nothing (or an unavailable model) is stored
  const selected = models.find((m) => m.id === selectedId) ?? models.find((m) => m.default) ?? models[0] ?? null;

  return { models, loading, selected, select: setSelectedId };
}
