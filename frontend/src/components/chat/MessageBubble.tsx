"use client";

import Markdown from "react-markdown";
import type { ChatMessage } from "@/lib/hooks/useChat";
import { ToolCallCard } from "./ToolCallCard";

interface MessageBubbleProps {
  message: ChatMessage;
}

function StreamingCursor() {
  return (
    <span className="ml-0.5 inline-block h-4 w-0.5 animate-pulse bg-gray-400" />
  );
}

function TypingDots() {
  return (
    <div className="flex items-center gap-1 py-1">
      <span className="h-2 w-2 animate-bounce rounded-full bg-gray-400 [animation-delay:0ms]" />
      <span className="h-2 w-2 animate-bounce rounded-full bg-gray-400 [animation-delay:150ms]" />
      <span className="h-2 w-2 animate-bounce rounded-full bg-gray-400 [animation-delay:300ms]" />
    </div>
  );
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === "user";
  const isTool = message.role === "tool";

  if (isUser) {
    return (
      <div className="flex justify-end">
        <div className="max-w-[75%] rounded-2xl rounded-br-md bg-indigo-600 px-4 py-2.5 text-white shadow-sm">
          <p className="whitespace-pre-wrap text-sm">{message.content}</p>
        </div>
      </div>
    );
  }

  if (isTool) {
    return (
      <div className="flex justify-start">
        <div className="max-w-[85%] rounded-md border border-gray-200 bg-gray-50 px-3 py-2 font-mono text-xs text-gray-700">
          <pre className="max-h-40 overflow-auto whitespace-pre-wrap">
            {message.content}
          </pre>
        </div>
      </div>
    );
  }

  // Assistant message
  const isStreamingEmpty = message.isStreaming && !message.content;
  const hasToolCalls = message.toolCalls && message.toolCalls.length > 0;

  return (
    <div className="flex justify-start">
      <div className="max-w-[85%] rounded-2xl rounded-bl-md border border-gray-200 bg-white px-4 py-2.5 shadow-sm">
        {hasToolCalls && (
          <div className="mb-2 space-y-2">
            {message.toolCalls!.map((tc, i) => (
              <ToolCallCard
                key={i}
                name={tc.name}
                args={tc.args}
                result={message.toolResults?.[i]?.result}
                isStreaming={message.isStreaming}
              />
            ))}
          </div>
        )}

        {isStreamingEmpty ? (
          <TypingDots />
        ) : (
          <div className="text-sm text-gray-800">
            <Markdown
              components={{
                h1: ({ children }) => (
                  <h1 className="mb-2 mt-3 text-lg font-bold first:mt-0">
                    {children}
                  </h1>
                ),
                h2: ({ children }) => (
                  <h2 className="mb-2 mt-3 text-base font-bold first:mt-0">
                    {children}
                  </h2>
                ),
                h3: ({ children }) => (
                  <h3 className="mb-1 mt-2 text-sm font-bold first:mt-0">
                    {children}
                  </h3>
                ),
                p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
                strong: ({ children }) => (
                  <strong className="font-semibold">{children}</strong>
                ),
                ul: ({ children }) => (
                  <ul className="mb-2 ml-4 list-disc space-y-0.5 last:mb-0">
                    {children}
                  </ul>
                ),
                ol: ({ children }) => (
                  <ol className="mb-2 ml-4 list-decimal space-y-0.5 last:mb-0">
                    {children}
                  </ol>
                ),
                li: ({ children }) => <li>{children}</li>,
                code: ({ children, className }) => {
                  const isBlock = className?.includes("language-");
                  if (isBlock) {
                    return (
                      <code className="block overflow-x-auto rounded bg-gray-100 p-2 font-mono text-xs">
                        {children}
                      </code>
                    );
                  }
                  return (
                    <code className="rounded bg-gray-100 px-1 py-0.5 font-mono text-xs">
                      {children}
                    </code>
                  );
                },
                pre: ({ children }) => <pre className="mb-2 last:mb-0">{children}</pre>,
                a: ({ href, children }) => (
                  <a
                    href={href}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-indigo-600 underline hover:text-indigo-500"
                  >
                    {children}
                  </a>
                ),
                blockquote: ({ children }) => (
                  <blockquote className="mb-2 border-l-2 border-gray-300 pl-3 italic text-gray-600 last:mb-0">
                    {children}
                  </blockquote>
                ),
                hr: () => <hr className="my-3 border-gray-200" />,
                table: ({ children }) => (
                  <div className="mb-2 overflow-x-auto last:mb-0">
                    <table className="min-w-full text-xs">{children}</table>
                  </div>
                ),
                thead: ({ children }) => (
                  <thead className="border-b border-gray-200 bg-gray-50">
                    {children}
                  </thead>
                ),
                th: ({ children }) => (
                  <th className="px-2 py-1 text-left font-semibold">
                    {children}
                  </th>
                ),
                td: ({ children }) => (
                  <td className="border-t border-gray-100 px-2 py-1">
                    {children}
                  </td>
                ),
              }}
            >
              {message.content}
            </Markdown>
            {message.isStreaming && <StreamingCursor />}
          </div>
        )}
      </div>
    </div>
  );
}
