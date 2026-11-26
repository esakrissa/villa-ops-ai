"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  ConnectionState,
  DisconnectReason,
  type Participant,
  type RemoteParticipant,
  type RemoteTrack,
  Room,
  RoomEvent,
  Track,
} from "livekit-client";
import { ApiError, apiFetch } from "@/lib/api";
import { readDisabledTools } from "./useAgentTools";

/** Villa voice mode: one LiveKit call with the Villa agent (see voice-agent/ in the repo). */

export type VoiceStatus = "idle" | "connecting" | "connected" | "error";
export type AgentState = "initializing" | "idle" | "listening" | "thinking" | "speaking" | "left";

export interface VoiceToolEvent {
  id: string;
  name: string;
  source?: string;
  args: Record<string, unknown>;
  status: "running" | "ok" | "error";
  result?: string;
  error?: string;
  seconds?: number;
}

export interface VoiceTurn {
  kind: "user" | "agent";
  id: string;
  text: string;
  final: boolean;
  typed?: boolean;
}

export type VoiceItem = VoiceTurn | { kind: "tool"; id: string };

interface SessionResponse {
  server_url: string;
  participant_token: string;
  room_name: string;
  conversation_id: string;
  model: string;
}

export interface VoiceModelOption {
  id: string;
  label: string;
  default: boolean;
}

interface VoiceConfig {
  enabled: boolean;
  agent_name: string;
  models: VoiceModelOption[];
  voice: string;
}

const TOOL_TOPIC = "villa.tool";
const CHAT_TOPIC = "lk.chat";
const MIC_TIMEOUT_MS = 8000;

/** Voice mode availability + models (GET /api/v1/voice/config). */
export function useVoiceConfig() {
  const [config, setConfig] = useState<VoiceConfig | null>(null);
  useEffect(() => {
    apiFetch<VoiceConfig>("/api/v1/voice/config")
      .then(setConfig)
      .catch(() => setConfig({ enabled: false, agent_name: "villa", models: [], voice: "" }));
  }, []);
  return config;
}

/** Audio level 0..1 from an analyser (RMS of the time-domain signal). */
function level(an: AnalyserNode | null, buf: Uint8Array<ArrayBuffer> | null): number {
  if (!an || !buf) return 0;
  an.getByteTimeDomainData(buf);
  let sum = 0;
  for (let i = 0; i < buf.length; i++) {
    const v = (buf[i] - 128) / 128;
    sum += v * v;
  }
  return Math.min(1, Math.sqrt(sum / buf.length) * 3.2);
}

export function useVoiceSession({ onEnded }: { onEnded?: (conversationId: string, hadTurns: boolean) => void } = {}) {
  const [status, setStatus] = useState<VoiceStatus>("idle");
  const [agentState, setAgentState] = useState<AgentState>("initializing");
  const [error, setError] = useState<string | null>(null);
  const [items, setItems] = useState<VoiceItem[]>([]);
  const [tools, setTools] = useState<Record<string, VoiceToolEvent>>({});
  const [muted, setMuted] = useState(false);
  const [micBlocked, setMicBlocked] = useState(false);
  const [micStarting, setMicStarting] = useState(false);
  const [audioBlocked, setAudioBlocked] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [model, setModel] = useState<string | null>(null);
  const [startedAt, setStartedAt] = useState<number | null>(null);

  const roomRef = useRef<Room | null>(null);
  const audioRootRef = useRef<HTMLDivElement | null>(null);
  const ctxRef = useRef<AudioContext | null>(null);
  const analysers = useRef<{ agent: AnalyserNode | null; user: AnalyserNode | null }>({ agent: null, user: null });
  const bufs = useRef<{ agent: Uint8Array<ArrayBuffer> | null; user: Uint8Array<ArrayBuffer> | null }>({ agent: null, user: null });
  const convRef = useRef<string | null>(null);
  const hadTurnsRef = useRef(false);
  const onEndedRef = useRef(onEnded);
  useEffect(() => {
    onEndedRef.current = onEnded;
  }, [onEnded]);

  const upsertTurn = useCallback((kind: "user" | "agent", id: string, text: string, final: boolean, typed = false) => {
    if (kind === "user") hadTurnsRef.current = true;
    setItems((prev) => {
      const i = prev.findIndex((it) => it.kind === kind && it.id === id);
      const item: VoiceTurn = { kind, id, text, final, typed };
      if (i === -1) return [...prev, item];
      const next = prev.slice();
      next[i] = item;
      return next;
    });
  }, []);

  const upsertTool = useCallback((ev: VoiceToolEvent) => {
    setTools((prev) => {
      const old = prev[ev.id];
      // Events arrive in order, but never let a late "running" undo a finished call
      if (old && old.status !== "running" && ev.status === "running") return prev;
      return { ...prev, [ev.id]: { ...old, ...ev } };
    });
    setItems((prev) => (prev.some((it) => it.kind === "tool" && it.id === ev.id) ? prev : [...prev, { kind: "tool", id: ev.id }]));
  }, []);

  const watched = useRef<{ agent: string | null; user: string | null }>({ agent: null, user: null });
  const watch = useCallback((who: "agent" | "user", track: MediaStreamTrack) => {
    if (watched.current[who] === track.id) return; // already analysed (a restarted mic is a new track)
    watched.current[who] = track.id;
    try {
      const ctx = (ctxRef.current ??= new AudioContext());
      const src = ctx.createMediaStreamSource(new MediaStream([track]));
      const an = ctx.createAnalyser();
      an.fftSize = 512;
      src.connect(an);
      analysers.current[who] = an;
      bufs.current[who] = new Uint8Array(new ArrayBuffer(an.fftSize));
    } catch (e) {
      console.warn("audio analyser unavailable", e);
    }
  }, []);

  /** Current speaking levels, read by the orb on every animation frame. */
  const getLevels = useCallback(
    () => ({
      agent: level(analysers.current.agent, bufs.current.agent),
      user: level(analysers.current.user, bufs.current.user),
    }),
    [],
  );

  const cleanup = useCallback(() => {
    roomRef.current = null;
    analysers.current = { agent: null, user: null };
    watched.current = { agent: null, user: null };
    ctxRef.current?.close().catch(() => {});
    ctxRef.current = null;
    audioRootRef.current?.remove();
    audioRootRef.current = null;
    setStartedAt(null);
  }, []);

  /**
   * The mute button mirrors the microphone track itself, never an assumption. Safari's permission
   * prompt can outlast our timeout: we used to mark the mic "blocked/muted" while it then went
   * live, so the button said muted while Villa could still hear you.
   */
  const syncMic = useCallback(
    (room: Room) => {
      const pub = room.localParticipant.getTrackPublication(Track.Source.Microphone);
      const live = !!pub?.track && !pub.isMuted;
      setMuted(!live);
      if (pub?.track) setMicBlocked(false);
      if (live && pub?.track?.mediaStreamTrack) watch("user", pub.track.mediaStreamTrack);
    },
    [watch],
  );

  const enableMic = useCallback(
    async (room: Room) => {
      setMicStarting(true);
      const enabling = room.localParticipant.setMicrophoneEnabled(true);
      // A slow permission prompt still resolves later: sync the button then
      void enabling.then(() => syncMic(room)).catch(() => syncMic(room));
      try {
        await Promise.race([
          enabling,
          new Promise((_, reject) => setTimeout(() => reject(new Error("The microphone didn't respond")), MIC_TIMEOUT_MS)),
        ]);
      } catch (e) {
        console.warn("microphone unavailable", e);
        setMicBlocked(!room.localParticipant.getTrackPublication(Track.Source.Microphone)?.track);
      }
      setMicStarting(false);
      syncMic(room);
    },
    [syncMic],
  );

  const start = useCallback(
    async (opts: { conversationId?: string | null; model?: string | null } = {}) => {
      if (roomRef.current) return;
      setError(null);
      setStatus("connecting");
      setAgentState("initializing");
      setItems([]);
      setTools({});
      hadTurnsRef.current = false;
      try {
        const sess = await apiFetch<SessionResponse>("/api/v1/voice/session", {
          method: "POST",
          body: JSON.stringify({
            conversation_id: opts.conversationId ?? null,
            model: opts.model ?? null,
            disabled_tools: readDisabledTools(),
          }),
        });
        convRef.current = sess.conversation_id;
        setConversationId(sess.conversation_id);
        setModel(sess.model);

        const room = new Room({
          adaptiveStream: true,
          dynacast: true,
          // Muting stops the mic track itself (Safari keeps recording a merely disabled track)
          publishDefaults: { stopMicTrackOnMute: true },
        });
        roomRef.current = room;
        const audioRoot = document.createElement("div");
        audioRoot.hidden = true;
        document.body.appendChild(audioRoot);
        audioRootRef.current = audioRoot;

        room
          .on(RoomEvent.TrackSubscribed, (track: RemoteTrack, _pub, participant: RemoteParticipant) => {
            if (track.kind !== Track.Kind.Audio) return;
            audioRoot.appendChild(track.attach());
            if (participant.isAgent && track.mediaStreamTrack) watch("agent", track.mediaStreamTrack);
          })
          .on(RoomEvent.TrackUnsubscribed, (track: RemoteTrack) => {
            track.detach().forEach((el) => el.remove());
          })
          .on(RoomEvent.ParticipantAttributesChanged, (changed: Record<string, string>, p: Participant) => {
            if ("lk.agent.state" in changed) setAgentState(p.attributes["lk.agent.state"] as AgentState);
          })
          .on(RoomEvent.ParticipantConnected, (p: RemoteParticipant) => {
            if (p.isAgent) setAgentState((p.attributes["lk.agent.state"] as AgentState) ?? "initializing");
          })
          .on(RoomEvent.ParticipantDisconnected, (p: RemoteParticipant) => {
            if (p.isAgent) setAgentState("left");
          })
          .on(RoomEvent.AudioPlaybackStatusChanged, () => setAudioBlocked(!room.canPlaybackAudio))
          .on(RoomEvent.LocalTrackPublished, () => syncMic(room))
          .on(RoomEvent.LocalTrackUnpublished, () => syncMic(room))
          .on(RoomEvent.TrackMuted, (_pub, p: Participant) => {
            if (p.identity === room.localParticipant.identity) syncMic(room);
          })
          .on(RoomEvent.TrackUnmuted, (_pub, p: Participant) => {
            if (p.identity === room.localParticipant.identity) syncMic(room);
          })
          .on(RoomEvent.Disconnected, (reason?: DisconnectReason) => {
            const conv = convRef.current;
            const hadTurns = hadTurnsRef.current;
            cleanup();
            setStatus("idle");
            if (reason !== undefined && reason !== DisconnectReason.CLIENT_INITIATED) {
              setError("The call dropped. Your conversation so far is saved.");
            }
            if (conv) onEndedRef.current?.(conv, hadTurns);
          });

        room.registerTextStreamHandler("lk.transcription", async (reader, participant) => {
          const attrs = reader.info.attributes ?? {};
          const segment = attrs["lk.segment_id"] ?? reader.info.id;
          if (participant.identity === room.localParticipant.identity) {
            const text = (await reader.readAll()).trim();
            if (text) upsertTurn("user", segment, text, attrs["lk.transcription_final"] === "true");
            return;
          }
          let text = "";
          for await (const chunk of reader) {
            text += chunk;
            upsertTurn("agent", segment, text, false);
          }
          if (text.trim()) upsertTurn("agent", segment, text.trim(), true);
        });

        room.registerTextStreamHandler(TOOL_TOPIC, async (reader) => {
          try {
            upsertTool(JSON.parse(await reader.readAll()) as VoiceToolEvent);
          } catch (e) {
            console.warn("bad tool event", e);
          }
        });

        await room.connect(sess.server_url, sess.participant_token);
        setStatus("connected");
        setStartedAt(Date.now());
        setAudioBlocked(!room.canPlaybackAudio);
        for (const p of room.remoteParticipants.values()) {
          if (p.isAgent) setAgentState((p.attributes["lk.agent.state"] as AgentState) ?? "initializing");
        }
        await enableMic(room);
      } catch (e) {
        console.error(e);
        await roomRef.current?.disconnect().catch(() => {});
        cleanup();
        setStatus("error");
        if (e instanceof ApiError && e.status === 402) setError("You've reached your plan's AI query limit. Upgrade to keep talking to Villa.");
        else if (e instanceof ApiError && e.status === 503) setError("Voice mode isn't configured on this server.");
        else setError(e instanceof Error ? e.message : "Couldn't start the call.");
      }
    },
    [cleanup, enableMic, syncMic, upsertTool, upsertTurn, watch],
  );

  const end = useCallback(async () => {
    const room = roomRef.current;
    if (!room) {
      setStatus("idle");
      return;
    }
    await room.disconnect();
  }, []);

  const muteBusy = useRef(false);
  const toggleMute = useCallback(async () => {
    const room = roomRef.current;
    if (!room || muteBusy.current) return;
    muteBusy.current = true;
    try {
      const pub = room.localParticipant.getTrackPublication(Track.Source.Microphone);
      if (!pub?.track) {
        await enableMic(room); // never got a mic (blocked / prompt dismissed): ask again
      } else if (pub.isMuted) {
        await room.localParticipant.setMicrophoneEnabled(true);
      } else {
        await room.localParticipant.setMicrophoneEnabled(false);
      }
    } catch (e) {
      console.warn("mute toggle failed", e);
    } finally {
      muteBusy.current = false;
      syncMic(room);
    }
  }, [enableMic, syncMic]);

  /** Type instead of speaking (prompt templates): the agent reads lk.chat like speech. */
  const sendText = useCallback(
    async (text: string) => {
      const room = roomRef.current;
      if (!room || room.state !== ConnectionState.Connected) return;
      upsertTurn("user", `typed-${Date.now()}`, text, true, true);
      await room.localParticipant.sendText(text, { topic: CHAT_TOPIC });
    },
    [upsertTurn],
  );

  const resumeAudio = useCallback(() => roomRef.current?.startAudio(), []);

  // Leave the room if the component goes away mid-call
  useEffect(() => () => void roomRef.current?.disconnect(), []);

  return {
    status,
    agentState,
    error,
    items,
    tools,
    muted,
    micBlocked,
    micStarting,
    audioBlocked,
    conversationId,
    model,
    startedAt,
    start,
    end,
    toggleMute,
    sendText,
    resumeAudio,
    getLevels,
    clearError: () => setError(null),
  };
}
