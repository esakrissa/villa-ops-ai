"use client";

import { useEffect, useRef } from "react";
import type { AgentState } from "@/lib/hooks/useVoiceSession";

const INK = "#2f2c25";
const LIME = "#d5f500";
const LIME_DEEP = "#b8d400";
const RING = "#d6cdbd";
const BARS = 64;

interface VoiceOrbProps {
  agentState: AgentState;
  connected: boolean;
  getLevels: () => { agent: number; user: number };
  size?: number;
}

/**
 * Villa's presence: an ink disc with a ring of bars. The ring follows whoever is talking —
 * lime for Villa, ink for the caller — and a sweep goes round while Villa thinks.
 */
export function VoiceOrb({ agentState, connected, getLevels, size = 260 }: VoiceOrbProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const stateRef = useRef(agentState);
  const connectedRef = useRef(connected);
  useEffect(() => {
    stateRef.current = agentState;
    connectedRef.current = connected;
  }, [agentState, connected]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = size * dpr;
    canvas.height = size * dpr;
    ctx.scale(dpr, dpr);

    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const smooth = new Float32Array(BARS);
    let agentLvl = 0;
    let userLvl = 0;
    let raf = 0;
    const t0 = performance.now();

    const draw = (now: number) => {
      const t = (now - t0) / 1000;
      const { agent, user } = getLevels();
      agentLvl += (agent - agentLvl) * 0.25;
      userLvl += (user - userLvl) * 0.25;
      const state = stateRef.current;
      const live = connectedRef.current;
      const speaking = state === "speaking";
      const active = speaking ? agentLvl : state === "listening" ? userLvl : 0;
      const color = speaking ? LIME_DEEP : INK;

      const c = size / 2;
      const base = size * 0.27;
      ctx.clearRect(0, 0, size, size);

      // Ring of bars
      for (let i = 0; i < BARS; i++) {
        const a = (i / BARS) * Math.PI * 2 - Math.PI / 2;
        const wobble = reduced ? 0.5 : 0.5 + 0.5 * Math.sin(t * 3 + i * 0.55) * Math.cos(t * 1.7 + i * 0.23);
        const target = live ? 0.08 + active * (0.55 + wobble * 0.9) : 0.05;
        smooth[i] += (target - smooth[i]) * 0.18;
        const len = 4 + smooth[i] * size * 0.16;
        const r0 = base + 14;
        ctx.strokeStyle = live && active > 0.04 ? color : RING;
        ctx.globalAlpha = live ? 0.35 + Math.min(0.65, smooth[i] * 2.2) : 0.5;
        ctx.lineWidth = 3;
        ctx.lineCap = "round";
        ctx.beginPath();
        ctx.moveTo(c + Math.cos(a) * r0, c + Math.sin(a) * r0);
        ctx.lineTo(c + Math.cos(a) * (r0 + len), c + Math.sin(a) * (r0 + len));
        ctx.stroke();
      }
      ctx.globalAlpha = 1;

      // Thinking sweep
      if (state === "thinking" && live) {
        const start = reduced ? 0 : (t * 2.4) % (Math.PI * 2);
        ctx.strokeStyle = LIME;
        ctx.lineWidth = 3;
        ctx.beginPath();
        ctx.arc(c, c, base + 6, start, start + Math.PI * 0.6);
        ctx.stroke();
      }

      // Disc (breathes with Villa's voice)
      const r = base * (1 + (speaking ? agentLvl * 0.12 : 0) + (reduced ? 0 : Math.sin(t * 1.4) * 0.01));
      const g = ctx.createRadialGradient(c - r * 0.35, c - r * 0.4, r * 0.1, c, c, r);
      g.addColorStop(0, "#4a443a");
      g.addColorStop(1, "#1f1d1b");
      ctx.fillStyle = g;
      ctx.beginPath();
      ctx.arc(c, c, r, 0, Math.PI * 2);
      ctx.fill();

      // Inner lime dot: lit while Villa speaks
      ctx.fillStyle = speaking ? LIME : state === "listening" && live ? "#625b50" : "#48433b";
      ctx.beginPath();
      ctx.arc(c, c, 5 + (speaking ? agentLvl * 10 : 0), 0, Math.PI * 2);
      ctx.fill();

      raf = requestAnimationFrame(draw);
    };
    raf = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(raf);
  }, [getLevels, size]);

  return <canvas ref={canvasRef} style={{ width: size, height: size }} className="max-w-full" aria-hidden="true" />;
}
