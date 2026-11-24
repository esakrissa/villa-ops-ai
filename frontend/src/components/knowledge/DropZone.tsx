"use client";

import { useRef, useState } from "react";
import { UploadIcon } from "@/components/ui/icons";

const ACCEPT = ".pdf,.docx,.md,.markdown,.txt";

export function DropZone({
  onFiles,
  onLoadSamples,
  disabled,
  maxMb,
}: {
  onFiles: (files: File[]) => void;
  onLoadSamples: () => void;
  disabled?: boolean;
  maxMb: number;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  const handle = (list: FileList | null) => {
    const files = Array.from(list ?? []);
    if (files.length) onFiles(files);
  };

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        if (!disabled) setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragging(false);
        if (!disabled) handle(e.dataTransfer.files);
      }}
      className={`relative flex flex-col items-center justify-center rounded-3xl border border-dashed px-6 py-8 text-center transition-colors ${
        dragging ? "border-ink bg-sand" : "border-gray-300 bg-white hover:border-gray-400"
      } ${disabled ? "pointer-events-none opacity-50" : ""}`}
    >
      <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-sand text-ink">
        <UploadIcon className="h-5 w-5" />
      </span>
      <p className="mt-3 text-[15px] font-medium text-ink">Drop company documents here</p>
      <p className="mt-1 text-[13px] text-gray-500">
        PDF, DOCX, Markdown or text · up to {maxMb} MB each
      </p>
      <div className="mt-4 flex flex-wrap items-center justify-center gap-2">
        <button type="button" className="btn-ink !py-2 !text-[13px]" onClick={() => inputRef.current?.click()}>
          Choose files
        </button>
        <button type="button" className="btn-sand !py-2 !text-[13px]" onClick={onLoadSamples}>
          Load sample documents
        </button>
      </div>
      <input
        ref={inputRef}
        type="file"
        accept={ACCEPT}
        multiple
        className="hidden"
        onChange={(e) => {
          handle(e.target.files);
          e.target.value = "";
        }}
      />
    </div>
  );
}
