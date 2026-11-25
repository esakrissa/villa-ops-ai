"use client";

import { useState } from "react";
import { ChevronIcon, MapPinIcon } from "@/components/ui/icons";

export interface ItineraryDay {
  day: number;
  title?: string;
  morning?: string;
  afternoon?: string;
  evening?: string;
  food?: string;
}

export interface Itinerary {
  kind: "itinerary";
  title: string;
  summary?: string;
  stay?: string;
  days: ItineraryDay[];
  tips?: string[];
}

export function parseItinerary(result?: string): Itinerary | null {
  if (!result) return null;
  try {
    const data = JSON.parse(result);
    return data && data.kind === "itinerary" && Array.isArray(data.days) ? (data as Itinerary) : null;
  } catch {
    return null;
  }
}

/** The latest itinerary among a message's tool results (Villa may revise it in one turn). */
export function latestItinerary(results?: { name: string; result: string }[]): Itinerary | null {
  if (!results) return null;
  for (let i = results.length - 1; i >= 0; i--) {
    if (results[i].name !== "show_itinerary") continue;
    const plan = parseItinerary(results[i].result);
    if (plan) return plan;
  }
  return null;
}

const SLOTS: { key: keyof ItineraryDay; label: string }[] = [
  { key: "morning", label: "Morning" },
  { key: "afternoon", label: "Afternoon" },
  { key: "evening", label: "Evening" },
  { key: "food", label: "Eat" },
];

/** Day-by-day trip plan written by Villa (voice) — also shown in the saved conversation. */
export function ItineraryCard({ plan, defaultOpen = true }: { plan: Itinerary; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <section className="overflow-hidden rounded-2xl border border-gray-200 bg-white">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="flex w-full items-start gap-3 px-5 pb-3 pt-4 text-left"
      >
        <span className="min-w-0 flex-1">
          <span className="eyebrow block text-gray-400">Itinerary · {plan.days.length} days</span>
          <span className="mt-1 block font-serif text-[24px] leading-tight text-ink">{plan.title}</span>
          {plan.summary && <span className="mt-1 block text-[13.5px] leading-relaxed text-gray-600">{plan.summary}</span>}
        </span>
        <ChevronIcon className={`mt-1 h-4 w-4 shrink-0 text-gray-400 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>

      {open && (
        <div className="border-t border-gray-100">
          {plan.stay && (
            <p className="flex items-start gap-2 bg-gray-50 px-5 py-2.5 text-[13px] text-gray-700">
              <MapPinIcon className="mt-0.5 h-3.5 w-3.5 shrink-0 text-gray-400" />
              <span>
                <span className="font-medium text-ink">Stay:</span> {plan.stay}
              </span>
            </p>
          )}
          <ol className="divide-y divide-gray-100">
            {plan.days.map((d, i) => (
              <li key={`${d.day}-${i}`} className="grid grid-cols-[3.25rem_1fr] gap-3 px-5 py-3.5">
                <div>
                  <span className="block font-mono text-[10.5px] uppercase tracking-wider text-gray-400">Day</span>
                  <span className="block font-serif text-[26px] leading-none text-ink">{d.day}</span>
                </div>
                <div className="min-w-0">
                  {d.title && <p className="text-[14px] font-semibold text-ink">{d.title}</p>}
                  <dl className="mt-1 grid gap-x-3 gap-y-0.5 text-[13px] leading-relaxed sm:grid-cols-[5rem_1fr]">
                    {SLOTS.filter((s) => d[s.key]).map((s) => (
                      <div key={s.key} className="contents">
                        <dt className="text-gray-400">{s.label}</dt>
                        <dd className="mb-1 text-gray-700 sm:mb-0">{String(d[s.key])}</dd>
                      </div>
                    ))}
                  </dl>
                </div>
              </li>
            ))}
          </ol>
          {!!plan.tips?.length && (
            <div className="border-t border-gray-100 bg-gray-50 px-5 py-3">
              <p className="eyebrow text-gray-400">Tips</p>
              <ul className="mt-1.5 space-y-1 text-[13px] text-gray-700">
                {plan.tips.map((t) => (
                  <li key={t} className="flex gap-2">
                    <span className="mt-[7px] h-1 w-1 shrink-0 rounded-full bg-lime-deep" />
                    {t}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
