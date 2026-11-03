"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { ArrowUpIcon, SparkIcon, StopIcon } from "@/components/ui/icons";

interface ChatInputProps {
  onSend: (message: string) => void;
  disabled?: boolean;
  isLoading?: boolean;
  onStop?: () => void;
  autoFocus?: boolean;
  placeholder?: string;
}

/** Floating composer card — textarea, model chip, send/stop button. */
export function ChatInput({
  onSend,
  disabled,
  isLoading,
  onStop,
  autoFocus,
  placeholder = "Ask about bookings, guests, properties…",
}: ChatInputProps) {
  const [input, setInput] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 220)}px`;
  }, [input]);

  useEffect(() => {
    if (autoFocus) textareaRef.current?.focus();
  }, [autoFocus]);

  const handleSend = useCallback(() => {
    const trimmed = input.trim();
    if (!trimmed || disabled || isLoading) return;
    onSend(trimmed);
    setInput("");
  }, [input, disabled, isLoading, onSend]);

  const canSend = !!input.trim() && !disabled && !isLoading;

  return (
    <div className="mx-auto w-full max-w-3xl">
      <div className="rounded-[26px] border border-gray-200 bg-white p-2 shadow-[0_8px_30px_-12px_rgb(47_44_37/0.18)] transition-[border-color,box-shadow] focus-within:border-gray-300 focus-within:shadow-[0_10px_40px_-12px_rgb(47_44_37/0.25)]">
        <textarea
          ref={textareaRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
              e.preventDefault();
              handleSend();
            }
          }}
          placeholder={placeholder}
          disabled={disabled}
          rows={1}
          className="block max-h-[220px] w-full resize-none bg-transparent px-3 pb-2 pt-2.5 text-[15px] leading-relaxed text-ink outline-none placeholder:text-gray-400 disabled:text-gray-400"
        />
        <div className="flex items-center justify-between gap-2 px-1">
          <div className="flex items-center gap-1.5">
            <span className="flex items-center gap-1.5 rounded-full bg-gray-100 px-2.5 py-1 text-[12px] text-gray-600">
              <SparkIcon className="h-3.5 w-3.5" />
              Gemini 3.5 Flash
            </span>
            <span className="hidden items-center gap-1.5 rounded-full px-2 py-1 text-[12px] text-gray-500 sm:flex">
              <span className="live-dot !h-1.5 !w-1.5" />
              15 tools
            </span>
          </div>
          {isLoading && onStop ? (
            <button
              type="button"
              onClick={onStop}
              title="Stop"
              className="flex h-9 w-9 items-center justify-center rounded-full bg-ink text-cream transition-transform active:scale-95"
            >
              <StopIcon className="h-[18px] w-[18px]" />
            </button>
          ) : (
            <button
              type="button"
              onClick={handleSend}
              disabled={!canSend}
              title="Send"
              className="flex h-9 w-9 items-center justify-center rounded-full bg-lime text-coal transition-[background,transform] hover:bg-lime-deep active:scale-95 disabled:bg-gray-100 disabled:text-gray-400"
            >
              <ArrowUpIcon className="h-4 w-4" />
            </button>
          )}
        </div>
      </div>
      <p className="mt-2 text-center text-[11.5px] text-gray-400">
        VillaOps asks before changing anything. Press <kbd className="font-mono">Enter</kbd> to send,{" "}
        <kbd className="font-mono">Shift + Enter</kbd> for a new line.
      </p>
    </div>
  );
}
