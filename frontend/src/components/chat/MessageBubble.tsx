"use client";

import { useState } from "react";
import Markdown from "react-markdown";
import type { ChatMessage } from "@/lib/hooks/useChat";
import { CheckIcon, CopyIcon } from "@/components/ui/icons";
import { LogoMark } from "@/components/ui/Logo";
import { ToolSteps } from "./ToolCallCard";
import { ConfirmationCard } from "./ConfirmationCard";
import { ListingResults } from "./ListingCards";

interface MessageBubbleProps {
  message: ChatMessage;
  /** False for follow-up assistant messages in the same turn */
  showAvatar?: boolean;
  onResumeConversation?: (action: "approve" | "cancel") => Promise<void>;
}

function Thinking() {
  return (
    <div className="flex h-7 items-center">
      <span className="shimmer-text text-[14px] font-medium">Thinking</span>
    </div>
  );
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      type="button"
      onClick={() => {
        navigator.clipboard?.writeText(text).then(() => {
          setCopied(true);
          setTimeout(() => setCopied(false), 1500);
        });
      }}
      title="Copy"
      className="rounded-lg p-1.5 text-gray-400 transition-colors hover:bg-gray-100 hover:text-ink"
    >
      {copied ? <CheckIcon className="h-3.5 w-3.5" /> : <CopyIcon className="h-3.5 w-3.5" />}
    </button>
  );
}

const markdownComponents = {
  h1: ({ children }: { children?: React.ReactNode }) => (
    <h1 className="mb-2 mt-5 font-serif text-[28px] leading-tight text-ink first:mt-0">{children}</h1>
  ),
  h2: ({ children }: { children?: React.ReactNode }) => (
    <h2 className="mb-2 mt-5 font-serif text-[24px] leading-tight text-ink first:mt-0">{children}</h2>
  ),
  h3: ({ children }: { children?: React.ReactNode }) => (
    <h3 className="mb-1.5 mt-4 text-[15px] font-semibold text-ink first:mt-0">{children}</h3>
  ),
  p: ({ children }: { children?: React.ReactNode }) => <p className="mb-3 last:mb-0">{children}</p>,
  strong: ({ children }: { children?: React.ReactNode }) => <strong className="font-semibold text-ink">{children}</strong>,
  ul: ({ children }: { children?: React.ReactNode }) => (
    <ul className="mb-3 ml-5 list-disc space-y-1 marker:text-gray-400 last:mb-0">{children}</ul>
  ),
  ol: ({ children }: { children?: React.ReactNode }) => (
    <ol className="mb-3 ml-5 list-decimal space-y-1 marker:text-gray-400 last:mb-0">{children}</ol>
  ),
  li: ({ children }: { children?: React.ReactNode }) => <li className="pl-1">{children}</li>,
  code: ({ children, className }: { children?: React.ReactNode; className?: string }) =>
    className?.includes("language-") ? (
      <code className="block overflow-x-auto rounded-xl bg-coal p-4 font-mono text-[12.5px] text-cream">{children}</code>
    ) : (
      <code className="rounded-md bg-sand px-1.5 py-0.5 font-mono text-[13px] text-ink">{children}</code>
    ),
  pre: ({ children }: { children?: React.ReactNode }) => <pre className="mb-3 last:mb-0">{children}</pre>,
  a: ({ href, children }: { href?: string; children?: React.ReactNode }) => (
    <a href={href} target="_blank" rel="noopener noreferrer" className="text-ink underline decoration-gray-300 underline-offset-2 hover:decoration-ink">
      {children}
    </a>
  ),
  blockquote: ({ children }: { children?: React.ReactNode }) => (
    <blockquote className="mb-3 border-l-2 border-lime pl-4 text-gray-600 last:mb-0">{children}</blockquote>
  ),
  hr: () => <hr className="my-5 border-gray-200" />,
  table: ({ children }: { children?: React.ReactNode }) => (
    <div className="mb-3 overflow-x-auto rounded-xl border border-gray-200 last:mb-0">
      <table className="min-w-full text-[13px]">{children}</table>
    </div>
  ),
  thead: ({ children }: { children?: React.ReactNode }) => <thead className="bg-gray-50">{children}</thead>,
  th: ({ children }: { children?: React.ReactNode }) => (
    <th className="px-3 py-2 text-left font-mono text-[11px] font-medium uppercase tracking-wider text-gray-500">{children}</th>
  ),
  td: ({ children }: { children?: React.ReactNode }) => <td className="border-t border-gray-100 px-3 py-2">{children}</td>,
};

export function MessageBubble({ message, showAvatar = true, onResumeConversation }: MessageBubbleProps) {
  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] rounded-3xl bg-sand px-5 py-3 text-[15px] leading-relaxed text-ink sm:max-w-[75%]">
          <p className="whitespace-pre-wrap">{message.content}</p>
        </div>
      </div>
    );
  }

  if (message.role === "tool") {
    return (
      <pre className="max-h-40 overflow-auto rounded-xl bg-gray-50 p-3 font-mono text-xs whitespace-pre-wrap text-gray-600">
        {message.content}
      </pre>
    );
  }

  const hasToolCalls = !!message.toolCalls?.length;
  const hasConfirmation = !!message.confirmation;
  const hasContent = !!message.content;
  const isThinking = message.isStreaming && !hasContent && !hasConfirmation && !hasToolCalls;
  const awaitingAnswer =
    message.isStreaming && hasToolCalls && !hasContent && message.toolCalls!.every((_, i) => message.toolResults?.[i]?.result);

  return (
    <div className={`group/msg flex gap-3.5 ${showAvatar ? "" : "-mt-6"}`}>
      <span className="flex h-7 w-7 shrink-0 items-center justify-center text-ink">
        {showAvatar && <LogoMark className="h-5 w-5" />}
      </span>

      <div className="min-w-0 flex-1">
        {hasToolCalls && (
          <ToolSteps toolCalls={message.toolCalls!} toolResults={message.toolResults} isStreaming={message.isStreaming} />
        )}

        <ListingResults toolResults={message.toolResults} />

        {hasConfirmation && (
          <div className="mb-3">
            <ConfirmationCard
              payload={message.confirmation!}
              onConfirm={() => onResumeConversation?.("approve")}
              onCancel={() => onResumeConversation?.("cancel")}
              isResolved={message.confirmationResolved}
              resolvedAction={message.confirmationAction}
            />
          </div>
        )}

        {(isThinking || awaitingAnswer) && <Thinking />}

        {hasContent && (
          <div className="pt-px text-[15px] leading-[1.7] text-gray-800">
            <Markdown components={markdownComponents}>{message.content}</Markdown>
            {message.isStreaming && (
              <span className="ml-0.5 inline-block h-[1.05em] w-[7px] translate-y-[3px] animate-pulse rounded-[2px] bg-lime" />
            )}
          </div>
        )}

        {hasContent && !message.isStreaming && (
          <div className="mt-1.5 flex items-center gap-1 opacity-0 transition-opacity group-hover/msg:opacity-100">
            <CopyButton text={message.content} />
          </div>
        )}
      </div>
    </div>
  );
}
