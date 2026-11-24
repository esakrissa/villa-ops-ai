"use client";

import { useState } from "react";
import { ArrowUpIcon, SearchIcon } from "@/components/ui/icons";
import { searchKnowledge, type SearchResponse } from "@/lib/hooks/useKnowledge";

const EXAMPLES = [
  "How long do we keep passport copies?",
  "Refund if a guest cancels 10 days before arrival",
  "Who approves compensation over IDR 500k?",
];

export function SearchPanel({ disabled, rerankModel }: { disabled?: boolean; rerankModel: string | null }) {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<SearchResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const run = async (q: string) => {
    const text = q.trim();
    if (!text) return;
    setQuery(text);
    setLoading(true);
    setError(null);
    try {
      setResult(await searchKnowledge(text, 4));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Search failed");
    } finally {
      setLoading(false);
    }
  };

  const top = result?.results[0]?.score ?? 1;

  return (
    <div className="panel p-5 sm:p-6">
      <p className="eyebrow text-gray-400">Test retrieval</p>
      <h2 className="mt-1 font-serif text-[24px] leading-tight text-ink">Ask what the agent would find</h2>
      <p className="mt-1 text-[13px] text-gray-500">
        Same search the agent&apos;s <span className="font-mono text-[12px]">kb_search</span> tool runs
        {rerankModel ? <> · reranked with <span className="font-mono text-[12px]">{rerankModel}</span></> : null}.
      </p>

      <form
        className="mt-4 flex items-center gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          void run(query);
        }}
      >
        <div className="relative flex-1">
          <SearchIcon className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
          <input
            className="field w-full !pl-10"
            placeholder="e.g. Can guests bring pets?"
            value={query}
            disabled={disabled}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
        <button
          type="submit"
          disabled={disabled || loading || !query.trim()}
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-ink text-cream transition-opacity disabled:opacity-40"
          aria-label="Search"
        >
          <ArrowUpIcon className="h-4 w-4" />
        </button>
      </form>

      <div className="mt-3 flex flex-wrap gap-1.5">
        {EXAMPLES.map((ex) => (
          <button
            key={ex}
            type="button"
            disabled={disabled || loading}
            onClick={() => void run(ex)}
            className="rounded-full border border-gray-200 bg-white px-3 py-1 text-[12px] text-gray-600 transition-colors hover:border-gray-300 hover:text-ink disabled:opacity-40"
          >
            {ex}
          </button>
        ))}
      </div>

      {error && <p className="mt-4 text-[13px] text-red-600">{error}</p>}

      {loading && (
        <div className="mt-5 space-y-2.5">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-20 animate-pulse rounded-2xl bg-gray-100/70" />
          ))}
        </div>
      )}

      {!loading && result && (
        <div className="mt-5">
          <p className="font-mono text-[11px] text-gray-400">
            {result.total} passages · {result.latency_ms} ms{result.reranked ? " · reranked" : ""}
          </p>
          {result.total === 0 ? (
            <p className="mt-3 text-[13px] text-gray-500">Nothing relevant in the knowledge base yet.</p>
          ) : (
            <ol className="mt-2.5 space-y-2.5">
              {result.results.map((r, i) => (
                <li
                  key={`${r.document_id}-${r.chunk}`}
                  className="rounded-2xl border border-gray-200/90 bg-white p-3.5 [animation:var(--animate-chunk-in)]"
                  style={{ animationDelay: `${i * 80}ms` }}
                >
                  <div className="flex items-center justify-between gap-3">
                    <p className="min-w-0 truncate text-[12.5px] text-ink">
                      <span className="font-medium">{r.document.replace(/\.[^.]+$/, "")}</span>
                      {r.section && <span className="text-gray-500"> › {r.section.split(" › ").slice(-1)[0]}</span>}
                      {r.page != null && <span className="text-gray-400"> · p.{r.page}</span>}
                    </p>
                    <div className="flex shrink-0 items-center gap-2">
                      <div className="h-1 w-14 overflow-hidden rounded-full bg-gray-100">
                        <div
                          className={`h-full rounded-full ${i === 0 ? "bg-lime-deep" : "bg-gray-400"}`}
                          style={{ width: `${Math.max(4, (r.score / (top || 1)) * 100)}%` }}
                        />
                      </div>
                      <span className="w-10 text-right font-mono text-[11px] tabular-nums text-gray-500">{r.score.toFixed(3)}</span>
                    </div>
                  </div>
                  <p className="mt-1.5 line-clamp-3 text-[12.5px] leading-relaxed text-gray-600">{r.text}</p>
                </li>
              ))}
            </ol>
          )}
        </div>
      )}
    </div>
  );
}
