"use client";

import { useEffect, useRef, useState } from "react";
import { SparkIcon } from "@/components/ui/icons";
import { useAgentModels } from "@/lib/hooks/useAgentModels";

/** Model chip in the composer; opens a small menu to switch the agent's LLM. */
export function ModelMenu() {
  const { models, loading, selected, select } = useAgentModels();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const label = selected?.label ?? (loading ? "Model" : "Default model");
  const canPick = models.length > 1;

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => canPick && setOpen((o) => !o)}
        aria-expanded={open}
        aria-haspopup="listbox"
        className={`flex items-center gap-1.5 rounded-full bg-gray-100 px-2.5 py-1 text-[12px] text-gray-600 transition-colors ${
          canPick ? "hover:bg-gray-200 hover:text-ink" : "cursor-default"
        }`}
      >
        <SparkIcon className="h-3.5 w-3.5" />
        {label}
        {canPick && (
          <svg viewBox="0 0 12 12" className={`h-2.5 w-2.5 transition-transform ${open ? "rotate-180" : ""}`} aria-hidden>
            <path d="M3 4.5 6 7.5 9 4.5" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        )}
      </button>

      {open && (
        <ul
          role="listbox"
          aria-label="Model"
          className="absolute bottom-full left-0 z-50 mb-2 w-[200px] overflow-hidden rounded-2xl border border-gray-200 bg-white py-1 shadow-[0_20px_50px_-20px_rgb(31_29_27/0.35)]"
        >
          {models.map((m) => {
            const active = m.id === selected?.id;
            return (
              <li key={m.id}>
                <button
                  type="button"
                  role="option"
                  aria-selected={active}
                  onClick={() => {
                    select(m.id);
                    setOpen(false);
                  }}
                  className="flex w-full items-center justify-between gap-3 px-4 py-2 text-left text-[13.5px] text-ink transition-colors hover:bg-gray-50"
                >
                  {m.label}
                  {active && <span className="h-1.5 w-1.5 rounded-full bg-lime" />}
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
