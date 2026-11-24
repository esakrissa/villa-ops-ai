"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { apiFetch } from "@/lib/api";
import { usePersistentState } from "./usePersistentState";

export interface AgentTool {
  name: string;
  description: string;
  source: "villaops" | "exa" | string;
}

export const DISABLED_TOOLS_KEY = "villaops.tools.disabled";

/** Read the user's disabled tools synchronously — used when sending a message. */
export function readDisabledTools(): string[] {
  try {
    const raw = window.localStorage.getItem(DISABLED_TOOLS_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed.filter((n) => typeof n === "string") : [];
  } catch {
    return [];
  }
}

const EMPTY: string[] = [];

/**
 * Tools the agent can use (discovered from the MCP servers) plus the user's
 * per-browser enable/disable choices. Disabled tools are sent with each chat
 * request and are not bound to the LLM.
 */
export function useAgentTools() {
  const [tools, setTools] = useState<AgentTool[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [disabledList, setDisabledList] = usePersistentState<string[]>(DISABLED_TOOLS_KEY, EMPTY);

  const disabled = useMemo(() => new Set(disabledList), [disabledList]);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setTools(await apiFetch<AgentTool[]>("/api/v1/chat/tools"));
    } catch {
      setError("Couldn't load tools");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // Initial load; state updates happen after the request resolves
    void refresh();
  }, [refresh]);

  const toggle = useCallback(
    (name: string) =>
      setDisabledList((prev) => (prev.includes(name) ? prev.filter((n) => n !== name) : [...prev, name])),
    [setDisabledList],
  );

  const setMany = useCallback(
    (names: string[], enabled: boolean) =>
      setDisabledList((prev) =>
        enabled ? prev.filter((n) => !names.includes(n)) : Array.from(new Set([...prev, ...names])),
      ),
    [setDisabledList],
  );

  const enabledCount = tools.filter((t) => !disabled.has(t.name)).length;

  return { tools, loading, error, disabled, toggle, setMany, enabledCount, refresh };
}
