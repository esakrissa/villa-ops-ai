"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { ConfirmModal } from "@/components/ui/ConfirmModal";
import { DocIcon, TrashIcon } from "@/components/ui/icons";
import { DropZone } from "@/components/knowledge/DropZone";
import { PipelineView } from "@/components/knowledge/PipelineView";
import { SearchPanel } from "@/components/knowledge/SearchPanel";
import {
  ACTIVE_STATUSES,
  deleteDocument,
  streamDocumentEvents,
  uploadDocument,
  useKnowledgeDocuments,
  type KnowledgeChunk,
  type KnowledgeDocument,
} from "@/lib/hooks/useKnowledge";

const SAMPLES = [
  "VillaOps Privacy Policy.md",
  "Guest House Rules and Booking Policy.md",
  "Staff Handbook - Operations.md",
];

const STATUS_LABEL: Record<string, string> = {
  queued: "Queued",
  extracting: "Extracting",
  chunking: "Chunking",
  indexing: "Indexing",
  verifying: "Verifying",
  ready: "Ready",
  failed: "Failed",
};

function formatBytes(n: number) {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

function StatusPill({ status }: { status: string }) {
  const active = ACTIVE_STATUSES.includes(status as KnowledgeDocument["status"]);
  const cls =
    status === "ready"
      ? "bg-sand text-ink"
      : status === "failed"
        ? "bg-red-50 text-red-700"
        : "bg-ink text-cream";
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 font-mono text-[10.5px] uppercase tracking-wide ${cls}`}>
      {active && <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-lime" />}
      {STATUS_LABEL[status] ?? status}
    </span>
  );
}

export default function KnowledgePage() {
  const { documents, status, loading, error, upsert, remove } = useKnowledgeDocuments();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [chunks, setChunks] = useState<KnowledgeChunk[]>([]);
  const [uploading, setUploading] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState<KnowledgeDocument | null>(null);
  const [deleting, setDeleting] = useState(false);
  const streamAbort = useRef<AbortController | null>(null);

  const selected = documents.find((d) => d.id === selectedId) ?? null;
  const enabled = status?.enabled ?? false;

  // Open the live event stream for the selected document. For finished documents
  // the stream replays every chunk and closes, so one code path handles both.
  const openStream = useCallback(
    (id: string) => {
      streamAbort.current?.abort();
      const ctrl = new AbortController();
      streamAbort.current = ctrl;
      setChunks([]);
      streamDocumentEvents(
        id,
        (e) => {
          if (e.type === "document") upsert(e.document);
          else if (e.type === "chunks") {
            const incoming = e.chunks.map((c, i) => ({ ...c, arrival: i }));
            setChunks((prev) => {
              const known = new Set(prev.map((c) => c.position));
              return [...prev, ...incoming.filter((c) => !known.has(c.position))].sort((a, b) => a.position - b.position);
            });
          } else if (e.type === "indexed") {
            const done = new Set(e.positions);
            setChunks((prev) => prev.map((c) => (done.has(c.position) ? { ...c, status: "indexed" } : c)));
          } else if (e.type === "done" && e.status === "deleted") {
            remove(id);
          }
        },
        ctrl.signal,
      ).catch((err) => {
        if (err?.name !== "AbortError") console.warn("Knowledge stream ended", err);
      });
    },
    [upsert, remove],
  );

  const select = useCallback(
    (id: string) => {
      setSelectedId(id);
      openStream(id);
    },
    [openStream],
  );

  // Auto-select the newest document on first load
  useEffect(() => {
    if (!selectedId && documents.length > 0) select(documents[0].id);
  }, [documents, selectedId, select]);

  useEffect(() => () => streamAbort.current?.abort(), []);

  const uploadFiles = async (files: File[]) => {
    setUploading(true);
    let first: KnowledgeDocument | null = null;
    for (const file of files) {
      try {
        const doc = await uploadDocument(file);
        upsert(doc);
        first ??= doc;
      } catch (err) {
        toast.error(`${file.name}: ${err instanceof Error ? err.message : "upload failed"}`);
      }
    }
    setUploading(false);
    if (first) select(first.id);
  };

  const loadSamples = async () => {
    try {
      const files = await Promise.all(
        SAMPLES.map(async (name) => {
          const res = await fetch(`/samples/${encodeURIComponent(name)}`);
          if (!res.ok) throw new Error(`Missing sample ${name}`);
          return new File([await res.blob()], name, { type: "text/markdown" });
        }),
      );
      await uploadFiles(files);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Couldn't load samples");
    }
  };

  const handleDelete = async () => {
    if (!confirmDelete) return;
    setDeleting(true);
    try {
      await deleteDocument(confirmDelete.id);
      remove(confirmDelete.id);
      if (selectedId === confirmDelete.id) {
        streamAbort.current?.abort();
        setSelectedId(null);
        setChunks([]);
      }
      toast.success(`Removed “${confirmDelete.name}” — the agent can no longer cite it`);
      setConfirmDelete(null);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Delete failed");
    } finally {
      setDeleting(false);
    }
  };

  const readyCount = documents.filter((d) => d.status === "ready").length;
  const totalChunks = documents.reduce((n, d) => n + d.chunk_count, 0);

  return (
    <div>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="display text-[44px] text-ink">Knowledge</h1>
          <p className="mt-1 text-sm text-gray-500">
            Company documents your agent can search and cite. Remove one and it&apos;s gone from answers instantly.
          </p>
        </div>
        {status && (
          <div className="flex flex-wrap gap-1.5 font-mono text-[11px] text-gray-600">
            <span className="rounded-full border border-gray-200 bg-white px-2.5 py-1">Pinecone · {status.index}</span>
            <span className="rounded-full border border-gray-200 bg-white px-2.5 py-1">{status.embed_model}</span>
            {status.rerank_model && (
              <span className="rounded-full border border-gray-200 bg-white px-2.5 py-1">{status.rerank_model}</span>
            )}
          </div>
        )}
      </div>

      {status && !status.enabled && (
        <div className="mb-6 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
          The knowledge base isn&apos;t configured. Set <span className="font-mono">PINECONE_API_KEY</span> on the backend.
        </div>
      )}
      {error && <div className="mb-6 rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">{error}</div>}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        {/* Left: upload + documents */}
        <div className="space-y-6 lg:col-span-5 xl:col-span-4">
          <DropZone
            onFiles={(f) => void uploadFiles(f)}
            onLoadSamples={() => void loadSamples()}
            disabled={!enabled || uploading}
            maxMb={status?.max_upload_mb ?? 10}
          />

          <div className="panel p-4">
            <div className="flex items-center justify-between px-1 pb-3">
              <p className="eyebrow text-gray-400">Documents</p>
              <p className="font-mono text-[11px] text-gray-400">
                {readyCount}/{documents.length} ready · {totalChunks} chunks
              </p>
            </div>
            {loading ? (
              <div className="space-y-2">
                {Array.from({ length: 3 }).map((_, i) => (
                  <div key={i} className="h-14 animate-pulse rounded-2xl bg-gray-100/70" />
                ))}
              </div>
            ) : documents.length === 0 ? (
              <p className="px-1 py-6 text-center text-[13px] text-gray-500">
                No documents yet. Upload a policy or load the samples.
              </p>
            ) : (
              <ul className="space-y-1">
                {documents.map((d) => (
                  <li key={d.id}>
                    <div
                      role="button"
                      tabIndex={0}
                      onClick={() => select(d.id)}
                      onKeyDown={(e) => e.key === "Enter" && select(d.id)}
                      className={`group flex cursor-pointer items-center gap-3 rounded-2xl px-3 py-2.5 transition-colors ${
                        d.id === selectedId ? "bg-sand" : "hover:bg-gray-50"
                      }`}
                    >
                      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-white text-gray-500 ring-1 ring-gray-200">
                        <DocIcon className="h-4 w-4" />
                      </span>
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-[13.5px] font-medium text-ink">{d.name.replace(/\.[^.]+$/, "")}</p>
                        <p className="mt-0.5 font-mono text-[11px] text-gray-400">
                          {d.file_type.toUpperCase()} · {formatBytes(d.size_bytes)}
                          {d.chunk_count > 0 && ` · ${d.chunk_count} chunks`}
                        </p>
                      </div>
                      <StatusPill status={d.status} />
                      <button
                        type="button"
                        title="Remove document"
                        onClick={(e) => {
                          e.stopPropagation();
                          setConfirmDelete(d);
                        }}
                        className="rounded-lg p-1.5 text-gray-400 opacity-0 transition-all hover:bg-white hover:text-red-600 group-hover:opacity-100 focus:opacity-100"
                      >
                        <TrashIcon className="h-4 w-4" />
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>

        {/* Right: pipeline + retrieval */}
        <div className="space-y-6 lg:col-span-7 xl:col-span-8">
          {selected ? (
            <PipelineView
              doc={selected}
              chunks={chunks}
              embedModel={status?.embed_model ?? ""}
              chunkTokens={status?.chunk_tokens ?? 350}
              overlapTokens={status?.overlap_tokens ?? 50}
            />
          ) : (
            <div className="panel flex min-h-[280px] flex-col items-center justify-center p-8 text-center">
              <p className="font-serif text-[26px] text-ink">Watch a document become searchable</p>
              <p className="mt-2 max-w-md text-[13.5px] text-gray-500">
                Upload a file and follow it through extraction, heading-aware chunking, embedding in Pinecone and a
                final search check — chunk by chunk.
              </p>
            </div>
          )}
          <SearchPanel disabled={!enabled || readyCount === 0} rerankModel={status?.rerank_model ?? null} />
        </div>
      </div>

      <ConfirmModal
        open={!!confirmDelete}
        title="Remove document?"
        description={`“${confirmDelete?.name ?? ""}” and its ${confirmDelete?.chunk_count ?? 0} chunks will be deleted from Pinecone and the database. The agent won't be able to cite it anymore.`}
        confirmLabel={deleting ? "Removing…" : "Remove"}
        destructive
        onConfirm={() => void handleDelete()}
        onCancel={() => setConfirmDelete(null)}
      />
    </div>
  );
}
