"use client";

import { useEffect, useRef, useState, type CSSProperties } from "react";
import { PlusIcon } from "@/components/ui/icons";
import type { AgentTool } from "@/lib/hooks/useAgentTools";
import { useAgentTools } from "@/lib/hooks/useAgentTools";
import { humanizeToolName } from "@/lib/toolLabels";

const SOURCES: Record<string, string> = {
  villaops: "VillaOps",
  booking: "Market · Booking.com",
  airbnb: "Market · Airbnb",
  tripadvisor: "Places · Tripadvisor",
  exa: "Web search · Exa",
};

function Switch({ on, onChange, label }: { on: boolean; onChange: () => void; label: string }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      aria-label={label}
      onClick={onChange}
      className={`relative h-[22px] w-[38px] shrink-0 rounded-full transition-colors duration-150 ${
        on ? "bg-ink" : "bg-gray-200"
      }`}
    >
      <span
        className={`absolute left-0 top-[3px] h-4 w-4 rounded-full shadow-sm transition-transform duration-150 ${
          on ? "translate-x-[19px] bg-lime" : "translate-x-[3px] bg-white"
        }`}
      />
    </button>
  );
}

/** "N tools" chip in the composer; opens a menu to switch tools on and off. */
export function ToolsMenu() {
  const { tools, loading, error, disabled, toggle, setMany, enabledCount, refresh } = useAgentTools();
  const [open, setOpen] = useState(false);
  const [panelStyle, setPanelStyle] = useState<CSSProperties>({});
  const ref = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);

  /** Fixed-position the panel next to the chip so scroll containers can't clip it. */
  function openMenu() {
    const rect = buttonRef.current?.getBoundingClientRect();
    if (rect) {
      const gap = 8;
      const spaceAbove = rect.top - gap * 2;
      const spaceBelow = window.innerHeight - rect.bottom - gap * 2;
      const up = spaceAbove >= Math.min(spaceBelow, 420) || spaceAbove > 420;
      const left = Math.min(rect.left, window.innerWidth - 320 - gap);
      setPanelStyle(
        up
          ? { left, bottom: window.innerHeight - rect.top + gap, maxHeight: Math.min(spaceAbove, 480) }
          : { left, top: rect.bottom + gap, maxHeight: Math.min(spaceBelow, 480) },
      );
    }
    setOpen(true);
  }

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    const onResize = () => setOpen(false);
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    window.addEventListener("resize", onResize);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
      window.removeEventListener("resize", onResize);
    };
  }, [open]);

  const groups = Object.entries(
    tools.reduce<Record<string, AgentTool[]>>((acc, t) => {
      (acc[t.source] ||= []).push(t);
      return acc;
    }, {}),
  );

  return (
    <div ref={ref} className="relative">
      <button
        ref={buttonRef}
        type="button"
        onClick={() => (open ? setOpen(false) : openMenu())}
        aria-expanded={open}
        aria-haspopup="dialog"
        className={`flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[12px] transition-colors ${
          open ? "bg-gray-100 text-ink" : "text-gray-500 hover:bg-gray-100 hover:text-ink"
        }`}
      >
        <span className={`live-dot !h-1.5 !w-1.5 ${enabledCount === 0 && !loading ? "!bg-gray-300 !animate-none" : ""}`} />
        {loading ? "Tools" : `${enabledCount} ${enabledCount === 1 ? "tool" : "tools"}`}
        <PlusIcon className={`h-3 w-3 transition-[rotate] duration-200 ${open ? "rotate-45" : ""}`} />
      </button>

      {open && (
        <div
          role="dialog"
          aria-label="Agent tools"
          style={panelStyle}
          className="fixed z-50 flex w-[320px] flex-col overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-[0_20px_50px_-20px_rgb(31_29_27/0.35)]"
        >
          <div className="flex items-center justify-between border-b border-gray-100 px-4 py-3">
            <div>
              <p className="text-[14px] font-medium text-ink">Tools</p>
              <p className="text-[12px] text-gray-500">
                {enabledCount} of {tools.length} on
              </p>
            </div>
            {tools.length > 0 && (
              <button
                type="button"
                onClick={() => setMany(tools.map((t) => t.name), enabledCount !== tools.length)}
                className="whitespace-nowrap rounded-full px-2.5 py-1 text-[12px] text-gray-600 transition-colors hover:bg-gray-100 hover:text-ink"
              >
                {enabledCount === tools.length ? "Turn all off" : "Turn all on"}
              </button>
            )}
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto py-1">
            {loading ? (
              <div className="space-y-2 p-4">
                {[0, 1, 2, 3].map((i) => (
                  <div key={i} className="h-7 animate-pulse rounded-lg bg-gray-100" />
                ))}
              </div>
            ) : error ? (
              <div className="p-4 text-center text-[13px] text-gray-500">
                {error}.{" "}
                <button type="button" onClick={refresh} className="font-medium text-ink underline underline-offset-2">
                  Retry
                </button>
              </div>
            ) : (
              groups.map(([source, items]) => {
                const groupOn = items.some((t) => !disabled.has(t.name));
                return (
                  <section key={source} className="py-1">
                    <div className="flex items-center justify-between px-4 py-2">
                      <p className="eyebrow !text-[10px] text-gray-400">{SOURCES[source] ?? source}</p>
                      <Switch
                        on={groupOn}
                        label={`${SOURCES[source] ?? source} tools`}
                        onChange={() => setMany(items.map((t) => t.name), !groupOn)}
                      />
                    </div>
                    <ul>
                      {items.map((t) => {
                        const on = !disabled.has(t.name);
                        return (
                          <li
                            key={t.name}
                            className="flex items-center gap-3 px-4 py-2 transition-colors hover:bg-gray-50"
                            title={t.description}
                          >
                            <div className="min-w-0 flex-1">
                              <p className={`truncate text-[13.5px] ${on ? "text-ink" : "text-gray-400"}`}>
                                {humanizeToolName(t.name)}
                              </p>
                              <p className="truncate text-[11.5px] text-gray-400">{t.description}</p>
                            </div>
                            <Switch on={on} label={humanizeToolName(t.name)} onChange={() => toggle(t.name)} />
                          </li>
                        );
                      })}
                    </ul>
                  </section>
                );
              })
            )}
          </div>

          {!loading && enabledCount === 0 && tools.length > 0 && (
            <p className="border-t border-gray-100 bg-gray-50 px-4 py-2.5 text-[12px] text-gray-500">
              All tools are off, so the agent will answer without looking anything up.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
