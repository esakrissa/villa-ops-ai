"use client";

import { useState } from "react";
import { orderedGroups, TEXT_GROUP_ORDER, VOICE_GROUP_ORDER } from "@/lib/promptTemplates";

interface PromptTemplatesProps {
  onPick: (prompt: string) => void;
  variant?: "text" | "voice";
  disabled?: boolean;
  /** Compact = one scrollable row of chips (under the composer); full = grid of cards */
  compact?: boolean;
}

/** Category tabs + prompt chips. Shared by the text chat and Villa's voice mode. */
export function PromptTemplates({ onPick, variant = "text", disabled, compact }: PromptTemplatesProps) {
  const groups = orderedGroups(variant === "voice" ? VOICE_GROUP_ORDER : TEXT_GROUP_ORDER);
  const [active, setActive] = useState(groups[0].id);
  const group = groups.find((g) => g.id === active) ?? groups[0];

  return (
    <div className="w-full">
      <div className="no-scrollbar -mx-1 flex gap-1 overflow-x-auto px-1 pb-2" role="tablist" aria-label="Prompt categories">
        {groups.map((g) => (
          <button
            key={g.id}
            type="button"
            role="tab"
            aria-selected={g.id === group.id}
            onClick={() => setActive(g.id)}
            className={`shrink-0 rounded-full px-3 py-1 text-[12.5px] transition-colors ${
              g.id === group.id ? "bg-ink text-cream" : "text-gray-500 hover:bg-gray-100 hover:text-ink"
            }`}
          >
            {g.label}
          </button>
        ))}
      </div>
      <div className={compact ? "flex flex-wrap gap-1.5" : "grid grid-cols-1 gap-2 sm:grid-cols-2"}>
        {group.templates.map((t) =>
          compact ? (
            <button
              key={t.prompt}
              type="button"
              disabled={disabled}
              onClick={() => onPick(t.prompt)}
              title={t.prompt}
              className="rounded-full border border-gray-200 bg-white/70 px-3 py-1.5 text-[13px] text-gray-700 transition-colors hover:border-gray-300 hover:bg-white hover:text-ink disabled:opacity-50"
            >
              {t.title}
            </button>
          ) : (
            <button
              key={t.prompt}
              type="button"
              disabled={disabled}
              onClick={() => onPick(t.prompt)}
              className="group rounded-2xl border border-gray-200 bg-white/60 px-4 py-3 text-left transition-colors hover:border-gray-300 hover:bg-white disabled:opacity-50"
            >
              <span className="block text-[14px] font-medium text-ink">{t.title}</span>
              <span className="block truncate text-[13px] text-gray-500">{t.prompt}</span>
            </button>
          ),
        )}
      </div>
    </div>
  );
}
