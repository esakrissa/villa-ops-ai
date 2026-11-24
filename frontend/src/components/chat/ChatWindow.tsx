"use client";

import { useEffect, useRef } from "react";
import { MessageBubble } from "./MessageBubble";
import type { ChatMessage } from "@/lib/hooks/useChat";

interface ChatWindowProps {
  messages: ChatMessage[];
  onResumeConversation?: (action: "approve" | "cancel") => Promise<void>;
}

export function ChatWindow({ messages, onResumeConversation }: ChatWindowProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages]);

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-8 px-4 pb-10 pt-8 sm:px-6">
      {messages.map((message, i) => (
        <MessageBubble
          key={message.id}
          message={message}
          showAvatar={messages[i - 1]?.role !== "assistant"}
          onResumeConversation={onResumeConversation}
        />
      ))}
      <div ref={bottomRef} />
    </div>
  );
}
