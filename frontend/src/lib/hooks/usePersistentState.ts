"use client";

import { useCallback, useSyncExternalStore } from "react";

const EVENT = "villaops:storage";

function subscribe(callback: () => void) {
  window.addEventListener("storage", callback);
  window.addEventListener(EVENT, callback);
  return () => {
    window.removeEventListener("storage", callback);
    window.removeEventListener(EVENT, callback);
  };
}

function read(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

/**
 * State backed by localStorage — for per-browser UI preferences such as
 * collapsed panels. The server snapshot is the default, so SSR and the first
 * client render match.
 */
export function usePersistentState<T>(key: string, initial: T) {
  const raw = useSyncExternalStore(
    subscribe,
    () => read(key),
    () => null,
  );

  let value = initial;
  if (raw !== null) {
    try {
      value = JSON.parse(raw) as T;
    } catch {
      // corrupt value — fall back to the default
    }
  }

  const update = useCallback(
    (next: T | ((prev: T) => T)) => {
      const current = read(key);
      const prev = current !== null ? (JSON.parse(current) as T) : initial;
      const resolved = typeof next === "function" ? (next as (p: T) => T)(prev) : next;
      try {
        window.localStorage.setItem(key, JSON.stringify(resolved));
      } catch {
        // storage unavailable — nothing to persist
      }
      window.dispatchEvent(new Event(EVENT));
    },
    [key, initial],
  );

  return [value, update] as const;
}

/** True when the viewport matches the media query (false during SSR). */
export function useMediaQuery(query: string): boolean {
  return useSyncExternalStore(
    (callback) => {
      const mql = window.matchMedia(query);
      mql.addEventListener("change", callback);
      return () => mql.removeEventListener("change", callback);
    },
    () => window.matchMedia(query).matches,
    () => false,
  );
}
