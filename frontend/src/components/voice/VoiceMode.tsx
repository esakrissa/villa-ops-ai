"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { ToolSteps } from "@/components/chat/ToolCallCard";
import { ListingResults } from "@/components/chat/ListingCards";
import { ItineraryCard, latestItinerary } from "@/components/chat/ItineraryCard";
import { PromptTemplates } from "@/components/chat/PromptTemplates";
import { ArrowUpIcon, ChevronIcon, CloseIcon, MicIcon, MicOffIcon, PhoneOffIcon } from "@/components/ui/icons";
import { usePersistentState } from "@/lib/hooks/usePersistentState";
import {
  type AgentState,
  useVoiceConfig,
  useVoiceSession,
  type VoiceItem,
  type VoiceToolEvent,
  type VoiceTurn,
} from "@/lib/hooks/useVoiceSession";
import { VoiceOrb } from "./VoiceOrb";

interface VoiceModeProps {
  /** The open chat, continued by voice; null starts a new conversation */
  conversationId: string | null;
  /** Called when the call ends (or never started) — the chat then shows the saved transcript */
  onExit: (conversationId: string | null, hadTurns: boolean) => void;
}

interface Block {
  key: string;
  question?: VoiceTurn;
  answers: VoiceTurn[];
  tools: VoiceToolEvent[];
}

/** Group the call into question → answer blocks (an FAQ of the call), tools under their answer. */
function toBlocks(items: VoiceItem[], tools: Record<string, VoiceToolEvent>): Block[] {
  const blocks: Block[] = [];
  let cur: Block = { key: "intro", answers: [], tools: [] };
  for (const it of items) {
    if (it.kind === "user") {
      // Consecutive spoken fragments before Villa answers belong to one question
      if (cur.question && !cur.answers.length && !cur.tools.length) {
        cur = { ...cur, question: { ...cur.question, text: `${cur.question.text} ${it.text}` } };
        continue;
      }
      if (cur.question || cur.answers.length || cur.tools.length) blocks.push(cur);
      cur = { key: it.id, question: it, answers: [], tools: [] };
    } else if (it.kind === "agent") {
      cur.answers.push(it);
    } else if (tools[it.id]) {
      cur.tools.push(tools[it.id]);
    }
  }
  if (cur.question || cur.answers.length || cur.tools.length) blocks.push(cur);
  return blocks;
}

function stateLabel(state: AgentState, status: string, muted: boolean): string {
  if (status === "connecting") return "Connecting to Villa…";
  if (status !== "connected") return "Call ended";
  switch (state) {
    case "initializing":
      return "Villa is joining…";
    case "listening":
      return muted ? "You're muted" : "Listening";
    case "thinking":
      return "Thinking…";
    case "speaking":
      return "Villa is speaking";
    case "left":
      return "Villa left the call";
    default:
      return "Ready";
  }
}

function useElapsed(startedAt: number | null): string {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!startedAt) return;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [startedAt]);
  if (!startedAt) return "0:00";
  const s = Math.max(0, Math.floor((now - startedAt) / 1000));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

function AnswerBlock({ block }: { block: Block }) {
  const toolCalls = block.tools.map((t) => ({ name: t.name, args: t.args ?? {} }));
  const toolResults = block.tools.map((t) => ({
    name: t.name,
    result: t.status === "ok" ? (t.result ?? "") : t.status === "error" ? `Error: ${t.error ?? "failed"}` : "",
  }));
  const running = block.tools.some((t) => t.status === "running");
  const plan = latestItinerary(toolResults);
  const text = block.answers.map((a) => a.text).join(" ");

  return (
    <article className="animate-fade-up border-b border-gray-200/70 pb-6 last:border-0">
      {block.question && (
        <div className="mb-3 flex gap-3">
          <span className="mt-0.5 font-mono text-[11px] font-medium text-gray-400">Q</span>
          <p className="text-[15px] font-medium leading-snug text-ink">
            {block.question.text}
            {block.question.typed && <span className="ml-2 align-middle font-mono text-[10px] uppercase tracking-wider text-gray-400">typed</span>}
          </p>
        </div>
      )}
      <div className="flex gap-3">
        <span className="mt-0.5 font-mono text-[11px] font-medium text-gray-400">{block.question ? "A" : "·"}</span>
        <div className="min-w-0 flex-1">
          {!!toolCalls.length && <ToolSteps toolCalls={toolCalls} toolResults={toolResults} isStreaming={running} />}
          <ListingResults toolResults={toolResults.filter((r) => r.result && r.name !== "show_itinerary")} />
          {plan && (
            <div className="mb-3">
              <ItineraryCard plan={plan} />
            </div>
          )}
          {text ? (
            <p className="text-[15px] leading-[1.7] text-gray-800">{text}</p>
          ) : (
            running && <span className="shimmer-text text-[14px] font-medium">Working</span>
          )}
        </div>
      </div>
    </article>
  );
}

/** Villa — the realtime voice concierge. Replaces the chat column while a call is on. */
export function VoiceMode({ conversationId, onExit }: VoiceModeProps) {
  const config = useVoiceConfig();
  const [voiceModel, setVoiceModel] = usePersistentState<string>("villaops.voice.model", "");
  const [showTemplates, setShowTemplates] = usePersistentState<boolean>("villaops.voice.templates", true);
  const [draft, setDraft] = useState("");
  const startedRef = useRef(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  const v = useVoiceSession({ onEnded: (conv, hadTurns) => onExit(conv, hadTurns) });
  const elapsed = useElapsed(v.startedAt);
  const blocks = useMemo(() => toBlocks(v.items, v.tools), [v.items, v.tools]);
  const caption = [...v.items].reverse().find((i): i is VoiceTurn => i.kind === "agent");
  const connected = v.status === "connected";
  const models = config?.models ?? [];
  const selectedModel = models.find((m) => m.id === voiceModel) ?? models.find((m) => m.default) ?? models[0];

  // Start the call as soon as voice mode opens (the wave button is the "call" button)
  useEffect(() => {
    if (!config?.enabled || startedRef.current) return;
    startedRef.current = true;
    void v.start({ conversationId, model: selectedModel?.id ?? null });
  }, [config, conversationId, selectedModel, v]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [v.items, v.tools]);

  const send = (text: string) => {
    const t = text.trim();
    if (!t || !connected) return;
    void v.sendText(t);
    setDraft("");
  };

  const disabled = config && !config.enabled;

  return (
    <div className="flex min-h-0 min-w-0 flex-1 flex-col">
      {/* Compact call bar: always in view below xl, where the transcript scrolls under it */}
      <div className="mx-4 mb-2 flex items-center gap-3 rounded-[22px] border border-gray-200 bg-white py-2 pl-2 pr-3 shadow-[0_8px_30px_-12px_rgb(47_44_37/0.18)] sm:mx-6 xl:hidden">
        <VoiceOrb agentState={v.agentState} connected={connected} getLevels={v.getLevels} size={64} />
        <div className="min-w-0 flex-1">
          <p className={`text-[13.5px] font-medium ${v.agentState === "thinking" && connected ? "shimmer-text" : "text-ink"}`}>
            Villa · {disabled ? "voice mode is off" : stateLabel(v.agentState, v.status, v.muted)}
            <span className="ml-2 font-mono text-[12px] font-normal tabular-nums text-gray-400">{elapsed}</span>
          </p>
          <p className="truncate text-[13px] text-gray-500">{caption?.text ?? (connected ? "Say hello, or pick a prompt below." : "")}</p>
        </div>
        <button
          type="button"
          onClick={v.toggleMute}
          disabled={!connected}
          aria-pressed={v.muted}
          title={v.muted ? "Unmute" : "Mute"}
          className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full border transition-colors disabled:opacity-40 ${
            v.muted ? "border-ink bg-ink text-cream" : "border-gray-200 bg-white text-ink hover:border-gray-300"
          }`}
        >
          {v.muted ? <MicOffIcon className="h-[18px] w-[18px]" /> : <MicIcon className="h-[18px] w-[18px]" />}
        </button>
        <button
          type="button"
          onClick={() => (connected || v.status === "connecting" ? v.end() : onExit(v.conversationId, false))}
          title="End call"
          aria-label="End call"
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-[#b4442f] text-white transition-[background,transform] hover:bg-[#9c3a28] active:scale-95"
        >
          <PhoneOffIcon className="h-[18px] w-[18px]" />
        </button>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto overflow-x-hidden">
        <div className="mx-auto grid w-full min-w-0 max-w-6xl grid-cols-1 gap-6 px-4 pb-8 pt-2 sm:px-6 xl:grid-cols-[minmax(320px,380px)_minmax(0,1fr)] xl:gap-10">
          {/* Call card */}
          <section className="mx-auto w-full max-w-md xl:sticky xl:top-2 xl:max-w-none xl:self-start">
            <div className="rounded-[28px] border border-gray-200 bg-white px-5 pb-5 pt-4 shadow-[0_8px_30px_-12px_rgb(47_44_37/0.18)]">
              <div className="hidden xl:block">
              <div className="flex items-center justify-between">
                <div>
                  <p className="eyebrow text-gray-400">Voice concierge</p>
                  <h2 className="font-serif text-[30px] leading-none text-ink">Villa</h2>
                </div>
                <div className="text-right">
                  <p className="font-mono text-[13px] tabular-nums text-gray-600">{elapsed}</p>
                  <p className="text-[11.5px] text-gray-400">{config?.voice || "ElevenLabs"}</p>
                </div>
              </div>

              <div className="relative mx-auto mt-2 flex justify-center">
                <VoiceOrb agentState={v.agentState} connected={connected} getLevels={v.getLevels} size={240} />
              </div>

              <p className={`text-center text-[14px] font-medium ${v.agentState === "thinking" && connected ? "shimmer-text" : "text-ink"}`}>
                {disabled ? "Voice mode is off on this server" : stateLabel(v.agentState, v.status, v.muted)}
              </p>
              <p className="mx-auto mt-1 line-clamp-3 min-h-[3.9em] max-w-sm text-center text-[13.5px] leading-[1.3] text-gray-500">
                {caption?.text ?? (connected ? "Say hello, or pick a prompt below." : "")}
              </p>

              {v.audioBlocked && connected && (
                <button type="button" onClick={v.resumeAudio} className="mx-auto mt-2 block rounded-full bg-lime px-4 py-1.5 text-[13px] font-medium text-coal">
                  Tap to hear Villa
                </button>
              )}
              {v.micBlocked && connected && (
                <p className="mt-2 text-center text-[12.5px] text-clay">Microphone unavailable — allow it and tap the mic, or type below.</p>
              )}

              {/* Controls */}
              <div className="mt-4 flex items-center justify-center gap-3">
                <button
                  type="button"
                  onClick={v.toggleMute}
                  disabled={!connected}
                  aria-pressed={v.muted}
                  title={v.muted ? "Unmute" : "Mute"}
                  className={`flex h-12 w-12 items-center justify-center rounded-full border transition-colors disabled:opacity-40 ${
                    v.muted ? "border-ink bg-ink text-cream" : "border-gray-200 bg-white text-ink hover:border-gray-300"
                  }`}
                >
                  {v.muted ? <MicOffIcon className="h-5 w-5" /> : <MicIcon className="h-5 w-5" />}
                </button>
                <button
                  type="button"
                  onClick={() => (connected || v.status === "connecting" ? v.end() : onExit(v.conversationId, false))}
                  title="End call"
                  className="flex h-12 items-center gap-2 rounded-full bg-[#b4442f] px-5 text-[14px] font-medium text-white transition-[background,transform] hover:bg-[#9c3a28] active:scale-95"
                >
                  <PhoneOffIcon className="h-5 w-5" />
                  End call
                </button>
              </div>
              </div>

              {/* Type instead of talking */}
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  send(draft);
                }}
                className="flex items-center gap-2 rounded-full border border-gray-200 bg-gray-50 py-1 pl-4 pr-1 focus-within:border-gray-300 xl:mt-4"
              >
                <input
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  disabled={!connected}
                  placeholder="Type to Villa instead…"
                  className="min-w-0 flex-1 bg-transparent text-[14px] text-ink outline-none placeholder:text-gray-400"
                />
                <button
                  type="submit"
                  disabled={!connected || !draft.trim()}
                  title="Send"
                  className="flex h-8 w-8 items-center justify-center rounded-full bg-ink text-cream disabled:bg-gray-200 disabled:text-gray-400"
                >
                  <ArrowUpIcon className="h-3.5 w-3.5" />
                </button>
              </form>

              {!!models.length && (
                <label className="mt-3 flex items-center justify-between gap-2 text-[12.5px] text-gray-500">
                  <span>Model</span>
                  <select
                    value={selectedModel?.id ?? ""}
                    onChange={(e) => setVoiceModel(e.target.value)}
                    className="rounded-full border border-gray-200 bg-white px-2.5 py-1 text-[12.5px] text-ink outline-none"
                    title={connected ? "Applies to your next call" : undefined}
                  >
                    {models.map((m) => (
                      <option key={m.id} value={m.id}>
                        {m.label}
                        {m.default ? " (default)" : ""}
                      </option>
                    ))}
                  </select>
                </label>
              )}
              {connected && v.model && selectedModel && v.model !== selectedModel.id && (
                <p className="mt-1 text-right text-[11.5px] text-gray-400">Applies to your next call</p>
              )}
            </div>

            {/* Prompt templates */}
            <div className="mt-4">
              <button
                type="button"
                onClick={() => setShowTemplates(!showTemplates)}
                aria-expanded={showTemplates}
                className="flex w-full items-center justify-between px-1 text-[13px] font-medium text-gray-600 hover:text-ink"
              >
                <span>Try asking</span>
                <ChevronIcon className={`h-3.5 w-3.5 transition-transform ${showTemplates ? "rotate-180" : ""}`} />
              </button>
              {showTemplates && (
                <div className="mt-2">
                  <PromptTemplates variant="voice" compact disabled={!connected} onPick={send} />
                </div>
              )}
            </div>
          </section>

          {/* Transcript */}
          <section className="min-w-0">
            <div className="flex items-baseline justify-between border-b border-gray-200 pb-2">
              <h3 className="eyebrow text-gray-500">Transcript</h3>
              <span className="text-[12px] text-gray-400">Saved to this conversation</span>
            </div>

            {v.error && (
              <div className="mt-4 flex items-start justify-between gap-3 rounded-xl border border-red-200 bg-red-50 px-4 py-2.5 text-[13px] text-red-700">
                <span>{v.error}</span>
                <button type="button" onClick={v.clearError} className="text-red-400 hover:text-red-700" aria-label="Dismiss">
                  <CloseIcon className="h-4 w-4" />
                </button>
              </div>
            )}

            {blocks.length === 0 ? (
              <div className="py-16 text-center">
                <p className="font-serif text-[26px] text-ink">
                  {v.status === "connecting" ? "Calling Villa…" : "Villa will greet you in a moment."}
                </p>
                <p className="mx-auto mt-2 max-w-md text-[14px] text-gray-500">
                  Ask about your villas, bookings and policies, or plan a week in Ubud. Searches show up here as cards,
                  and itineraries as a day-by-day plan.
                </p>
              </div>
            ) : (
              <div className="mt-5 flex flex-col gap-6">
                {blocks.map((b) => (
                  <AnswerBlock key={b.key} block={b} />
                ))}
              </div>
            )}
            <div ref={bottomRef} />
          </section>
        </div>
      </div>
    </div>
  );
}
