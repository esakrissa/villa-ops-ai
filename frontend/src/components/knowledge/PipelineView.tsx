"use client";

import { CheckIcon } from "@/components/ui/icons";
import type { DocStatus, KnowledgeChunk, KnowledgeDocument } from "@/lib/hooks/useKnowledge";

const STAGES: { key: DocStatus; label: string; detail: string }[] = [
  { key: "extracting", label: "Extract", detail: "Read text, keep headings & pages" },
  { key: "chunking", label: "Chunk", detail: "Split by section with overlap" },
  { key: "indexing", label: "Embed & index", detail: "Pinecone embeds and stores" },
  { key: "verifying", label: "Verify", detail: "Confirm it's searchable" },
  { key: "ready", label: "Ready", detail: "Agent can cite it" },
];

const ORDER: DocStatus[] = ["queued", "extracting", "chunking", "indexing", "verifying", "ready"];

function stageState(doc: KnowledgeDocument, stage: DocStatus): "done" | "active" | "todo" | "failed" {
  if (doc.status === "failed") {
    // Mark the stage it failed in: the first one whose work isn't done
    const reached = doc.indexed_count > 0 ? 3 : doc.chunk_count > 0 ? 2 : doc.char_count > 0 ? 1 : 0;
    const idx = ORDER.indexOf(stage) - 1;
    if (idx < reached) return "done";
    return idx === reached ? "failed" : "todo";
  }
  const cur = ORDER.indexOf(doc.status);
  const idx = ORDER.indexOf(stage);
  if (doc.status === "ready" || idx < cur) return "done";
  return idx === cur ? "active" : "todo";
}

function Stepper({ doc }: { doc: KnowledgeDocument }) {
  return (
    <ol className="grid grid-cols-5 gap-1.5">
      {STAGES.map((s, i) => {
        const state = stageState(doc, s.key);
        return (
          <li key={s.key} className="min-w-0">
            <div
              className={`h-1 rounded-full transition-colors duration-500 ${
                state === "done"
                  ? "bg-ink"
                  : state === "active"
                    ? "shimmer-bar bg-gray-300"
                    : state === "failed"
                      ? "bg-red-500"
                      : "bg-gray-200"
              }`}
            />
            <div className="mt-2 flex items-center gap-1.5">
              <span
                className={`flex h-4 w-4 shrink-0 items-center justify-center rounded-full font-mono text-[9px] ${
                  state === "done"
                    ? "bg-ink text-cream"
                    : state === "active"
                      ? "bg-lime text-ink"
                      : state === "failed"
                        ? "bg-red-500 text-white"
                        : "bg-gray-100 text-gray-400"
                }`}
              >
                {state === "done" ? <CheckIcon className="h-2.5 w-2.5" /> : i + 1}
              </span>
              <span className={`truncate text-[12.5px] ${state === "todo" ? "text-gray-400" : "font-medium text-ink"}`}>
                {s.label}
              </span>
            </div>
            <p className="mt-0.5 hidden truncate pl-[22px] text-[11px] text-gray-400 xl:block">{s.detail}</p>
          </li>
        );
      })}
    </ol>
  );
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="min-w-0">
      <p className="eyebrow text-[10px] text-gray-400">{label}</p>
      <p className="mt-0.5 font-serif text-[22px] leading-none text-ink tabular-nums">{value}</p>
    </div>
  );
}

function ChunkCard({ chunk }: { chunk: KnowledgeChunk }) {
  const indexed = chunk.status === "indexed";
  const section = chunk.heading?.split(" › ").slice(-1)[0];
  return (
    <div
      className="flex min-h-[150px] flex-col rounded-2xl border border-gray-200/90 bg-white p-3.5 transition-[border-color,box-shadow] duration-500 [animation:var(--animate-chunk-in)]"
      style={{
        animationDelay: `${(chunk.arrival ?? 0) * 70}ms`,
        boxShadow: indexed ? "inset 0 0 0 1px rgb(47 44 37 / 0.08)" : undefined,
      }}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="font-mono text-[11px] text-gray-500">#{String(chunk.position + 1).padStart(2, "0")}</span>
        <span className="flex items-center gap-1.5 font-mono text-[10.5px] uppercase tracking-wide text-gray-500">
          <span
            className={`h-1.5 w-1.5 rounded-full transition-colors duration-500 ${
              indexed ? "bg-lime-deep" : "animate-pulse bg-gray-300"
            }`}
          />
          {indexed ? "indexed" : "pending"}
        </span>
      </div>
      {section && <p className="mt-2 truncate text-[12.5px] font-medium text-ink" title={chunk.heading ?? ""}>{section}</p>}
      <p className="mt-1 line-clamp-4 flex-1 text-[12.5px] leading-relaxed text-gray-600">{chunk.text}</p>
      <div className="mt-2.5 flex items-center gap-2 font-mono text-[10.5px] text-gray-400">
        <span>~{chunk.token_count} tok</span>
        {chunk.page != null && <span>· p.{chunk.page}</span>}
      </div>
    </div>
  );
}

export function PipelineView({
  doc,
  chunks,
  embedModel,
  chunkTokens,
  overlapTokens,
}: {
  doc: KnowledgeDocument;
  chunks: KnowledgeChunk[];
  embedModel: string;
  chunkTokens: number;
  overlapTokens: number;
}) {
  const pct = doc.chunk_count ? Math.round((doc.indexed_count / doc.chunk_count) * 100) : 0;
  return (
    <div className="panel p-5 sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="eyebrow text-gray-400">Ingestion pipeline</p>
          <h2 className="mt-1 truncate font-serif text-[28px] leading-tight text-ink">{doc.name.replace(/\.[^.]+$/, "")}</h2>
        </div>
        <p className="font-mono text-[11px] text-gray-500">
          {chunkTokens} tok chunks · {overlapTokens} overlap · {doc.embed_model ?? embedModel}
        </p>
      </div>

      <div className="mt-5">
        <Stepper doc={doc} />
      </div>

      {doc.status === "failed" && (
        <p className="mt-4 rounded-2xl bg-red-50 px-4 py-3 text-[13px] text-red-700">{doc.error ?? "Processing failed."}</p>
      )}

      <div className="mt-5 grid grid-cols-3 gap-4 border-y border-gray-100 py-4 sm:grid-cols-5">
        <Stat label="Pages" value={doc.page_count ?? "—"} />
        <Stat label="Characters" value={doc.char_count.toLocaleString()} />
        <Stat label="Tokens" value={doc.token_count ? `~${doc.token_count.toLocaleString()}` : "—"} />
        <Stat label="Chunks" value={doc.chunk_count} />
        <Stat label="Indexed" value={`${pct}%`} />
      </div>

      <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-gray-100">
        <div className="h-full rounded-full bg-ink transition-[width] duration-500 ease-out" style={{ width: `${pct}%` }} />
      </div>

      {chunks.length > 0 ? (
        <div className="mt-5 grid max-h-[560px] grid-cols-1 gap-3 overflow-y-auto pr-1 sm:grid-cols-2 2xl:grid-cols-3">
          {chunks.map((c) => (
            <ChunkCard key={c.position} chunk={c} />
          ))}
        </div>
      ) : (
        <div className="mt-5 grid grid-cols-1 gap-3 sm:grid-cols-2 2xl:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-[150px] animate-pulse rounded-2xl bg-gray-100/70" />
          ))}
        </div>
      )}
    </div>
  );
}
