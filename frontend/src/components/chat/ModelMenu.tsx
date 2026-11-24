"use client";

import { useEffect, useRef, useState } from "react";
import { SparkIcon } from "@/components/ui/icons";
import { useAgentModels } from "@/lib/hooks/useAgentModels";

/** Model chip in the composer; opens a small menu to switch the agent's LLM. */
export function ModelMenu() {
  const { models, loading, selected, select } = useAgentModels();
  const [open, setOpen] = useState(false);
  // Open upward unless there isn't room above the chip (e.g. composer near the top)
  const [dropUp, setDropUp] = useState(true);
  const [maxHeight, setMaxHeight] = useState(360);
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
        onClick={() => {
          if (!canPick) return;
          if (!open && ref.current) {
            const rect = ref.current.getBoundingClientRect();
            const above = rect.top - 16;
            const below = window.innerHeight - rect.bottom - 16;
            const up = above >= 260 || above >= below;
            setDropUp(up);
            setMaxHeight(Math.max(160, Math.min(380, (up ? above : below) - 8)));
          }
          setOpen((o) => !o);
        }}
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
          style={{ maxHeight }}
          className={`absolute left-0 z-50 w-[236px] overflow-y-auto overscroll-contain rounded-2xl border border-gray-200 bg-white py-1 shadow-[0_20px_50px_-20px_rgb(31_29_27/0.35)] ${
            dropUp ? "bottom-full mb-2" : "top-full mt-2"
          }`}
        >
          {models.map((m, i) => {
            const active = m.id === selected?.id;
            const free = m.label.includes("free");
            const prevFree = i > 0 && models[i - 1].label.includes("free");
            const header = i === 0 ? (free ? "Free" : "Paid") : free && !prevFree ? "Free" : null;
            return (
              <li key={m.id}>
                {header && (
                  <p className={`eyebrow px-4 pb-1 text-[10px] text-gray-400 ${i === 0 ? "pt-2" : "mt-1 border-t border-gray-100 pt-2.5"}`}>
                    {header}
                  </p>
                )}
                <button
                  type="button"
                  role="option"
                  aria-selected={active}
                  onClick={() => {
                    select(m.id);
                    setOpen(false);
                  }}
                  className={`flex w-full items-center justify-between gap-3 px-4 py-2 text-left text-[13.5px] text-ink transition-colors hover:bg-gray-50 ${
                    active ? "bg-gray-50" : ""
                  }`}
                >
                  <span className="truncate">{m.label.replace(/\s*·\s*free$/, "")}</span>
                  {active && <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-lime" />}
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
