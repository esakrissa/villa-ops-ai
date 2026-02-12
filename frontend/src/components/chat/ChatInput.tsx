"use client";

import { useState, useRef, useCallback, useEffect } from "react";

interface ChatInputProps {
  onSend: (message: string) => void;
  disabled?: boolean;
}

export function ChatInput({ onSend, disabled }: ChatInputProps) {
  const [input, setInput] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const resetHeight = useCallback(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 160)}px`;
    }
  }, []);

  useEffect(() => {
    resetHeight();
  }, [input, resetHeight]);

  const handleSend = useCallback(() => {
    const trimmed = input.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setInput("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  }, [input, disabled, onSend]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="mx-auto flex w-full max-w-3xl items-end gap-3">
      <div className="relative flex-1">
        <textarea
          ref={textareaRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask about bookings, guests, properties..."
          disabled={disabled}
          rows={1}
          className="w-full resize-none rounded-xl border border-gray-300 bg-white px-4 py-3 pr-12 text-sm text-gray-900 shadow-sm outline-none transition-colors placeholder:text-gray-400 focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100 disabled:bg-gray-50 disabled:text-gray-400"
        />
      </div>
      <button
        onClick={handleSend}
        disabled={!input.trim() || disabled}
        className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-indigo-600 text-white shadow-sm transition-colors hover:bg-indigo-700 disabled:bg-gray-300 disabled:text-gray-400"
      >
        <svg
          className="h-5 w-5"
          fill="none"
          viewBox="0 0 24 24"
          strokeWidth={2}
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M6 12 3.269 3.125A59.769 59.769 0 0 1 21.485 12 59.768 59.768 0 0 1 3.27 20.875L5.999 12Zm0 0h7.5"
          />
        </svg>
      </button>
    </div>
  );
}
