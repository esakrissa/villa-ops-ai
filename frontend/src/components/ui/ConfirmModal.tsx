"use client";

import { useEffect, useRef } from "react";

interface ConfirmModalProps {
  open: boolean;
  title: string;
  description: string;
  confirmLabel?: string;
  cancelLabel?: string;
  /** Red confirm button for irreversible actions like deletes */
  destructive?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmModal({
  open,
  title,
  description,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  destructive = false,
  onConfirm,
  onCancel,
}: ConfirmModalProps) {
  const confirmRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (open) {
      confirmRef.current?.focus();
    }
  }, [open]);

  useEffect(() => {
    if (!open) return;
    function handleKey(e: KeyboardEvent) {
      if (e.key === "Escape") onCancel();
    }
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [open, onCancel]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-coal/40 transition-opacity"
        onClick={onCancel}
      />

      {/* Modal */}
      <div className="relative mx-4 w-full max-w-md rounded-[28px] bg-cream p-7 shadow-[0_30px_60px_-20px_rgb(31_29_27/0.45)]">
        <h3 className="display text-[32px] text-ink">{title}</h3>
        <p className="mt-3 text-[14px] leading-relaxed text-gray-600">{description}</p>

        <div className="mt-7 flex justify-end gap-2">
          <button
            onClick={onCancel}
            className="btn-sand !py-2"
          >
            {cancelLabel}
          </button>
          <button
            ref={confirmRef}
            onClick={onConfirm}
            className={destructive ? "inline-flex items-center rounded-full bg-[#b4532a] px-5 py-2 text-[14px] font-medium text-white transition-colors hover:bg-[#9a4523]" : "btn-ink !py-2"}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
