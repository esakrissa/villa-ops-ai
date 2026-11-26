# Villa — the realtime voice agent

Villa is VillaOps' voice concierge. Press the **voice-wave button** in the chat composer and talk:
plan a week in Ubud (hotels, restaurants, attractions, a day-by-day itinerary on screen), or ask
about your villas, bookings, guests and company policies. Villa uses the same MCP tools as the text
agent, including the knowledge base, and every call is saved as an ordinary chat conversation.

## How it works

```
Browser (Next.js)                      LiveKit Cloud                 voice-agent (EC2, docker compose)
 voice-wave button                     (WebRTC SFU +                  LiveKit Agents 1.8 worker "villa"
   │ POST /api/v1/voice/session         agent dispatch)               ┌──────────────────────────────┐
   │   ← token (room + dispatch          │                             │ STT  AssemblyAI U-3.6 Pro    │
   │     metadata: user, conversation,   │  job + audio                │      (LiveKit Inference)     │
   │     model, tools switched off)      ├────────────────────────────▶│ LLM  Claude Haiku 5.5 via    │
   │                                     │                             │      OpenRouter → Gemini 3.1 │
   ├─ mic / Villa's voice ──── WebRTC ───┤                             │      Flash-Lite → GPT-4.1    │
   ├─ lk.transcription (live captions)   │◀────────────────────────────┤      mini (LiveKit Inference)│
   ├─ villa.tool (tool cards, itinerary) │                             │ TTS  ElevenLabs Flash v2.5   │
   └─ lk.chat (typed prompts/templates)  │                             │      → Fish Audio → Cartesia │
                                                                       │ Tools: MCP (user_id pinned)  │
FastAPI backend ◀── X-Voice-Agent-Key: transcript turns, history ──────┤  VillaOps · Booking · Airbnb │
  (conversation + messages + AI-query usage)                           │  Tripadvisor · Exa · show_   │
                                                                       │  itinerary                   │
                                                                       └──────────────────────────────┘
```

- **Token and identity.** `POST /api/v1/voice/session` (auth + AI-query plan limit) mints an HS256
  LiveKit token for a fresh room. Its `roomConfig` dispatches the `villa` agent with metadata
  `{user_id, conversation_id, model, disabled_tools}`. Only the backend holds the LiveKit secret,
  so the agent trusts that metadata and **pins `user_id` on every VillaOps tool call** — the
  model never sees or chooses it (the text agent passes it through the prompt instead).
- **Tools.** `villa/mcp_tools.py` discovers the MCP tools (cached per process, warmed at worker
  start) and wraps each as a LiveKit raw-schema tool with `user_id` stripped from the schema.
  Deletes aren't offered by voice (they need the text chat's confirmation card). Market search
  results are cut to the fields worth saying before the model reads them (~10 KB → ~2 KB); the
  page gets the full JSON for photo cards. Booking.com/Airbnb calls get a 12 s deadline (a cold
  RapidAPI search measured 23 s), Exa 8 s, others 20 s; at most one "one moment" filler per 12 s.
- **Itineraries.** `show_itinerary` takes a day-by-day plan (morning/afternoon/evening/eat), the
  page draws it as a card and Villa speaks a two-sentence summary. The same card renders in the
  saved conversation.
- **Transcript.** User turns, Villa's lines, tool calls and tool results are posted in order to
  `/api/v1/voice/internal/*` (shared secret; Caddy returns 404 for that path from outside). A new
  conversation is created by the first saved turn; the greeting is held until the caller speaks,
  so a call nobody speaks in leaves no empty chat. Each spoken question counts as one AI query.
  Continuing an existing chat by voice loads its last 16 turns as context.
- **Resilience.** Each model has a backup from another vendor (`llm.FallbackAdapter`,
  `tts.FallbackAdapter`, one pass per turn). A turn that fails on every LLM gets a spoken apology.
  The LLM attempt timeout is 15 s because the OpenAI plugin only hands over a tool call once its
  arguments are complete, and a 7-day itinerary call is ~1.4k tokens (~7 s on Haiku 5.5); at 6 s
  the itinerary was cut off silently.
- **No sound effects.** Villa's voice is the only audio; the orb and the "Thinking…" label show
  that she's working. Muting stops the microphone track itself (`stopMicTrackOnMute`), and the mute
  button mirrors the track's real state (Safari's slow permission prompt used to leave the button
  saying "muted" while the mic was live).
- **UI.** Voice mode replaces the chat column: Villa's orb (lime ring when she speaks, ink when you
  do, a sweep while she thinks), live caption, mute / end call, a "type instead" box, the voice
  model picker and prompt templates; the transcript reads as Q → A blocks with tool steps, photo
  cards and the itinerary card. Below 1280 px a compact call bar stays pinned while the
  transcript scrolls. Ending the call opens the saved conversation in the text chat.

## Models (chosen by measurement, 2026-11-25)

LLM, one voice step on the real prompt and 23 tools, 8 runs each via OpenRouter — all picked the
right tool 8/8:

| Model | Time to first token p50 (max) | $ / M tokens in / out |
|---|---|---|
| Gemini 3.1 Flash-Lite | **0.84 s** (1.17) | 0.25 / 1.50 |
| **Claude Haiku 5.5 (default)** | 1.02 s (1.59) | **0.10 / 0.50** |
| GPT-6 Sol | 1.06 s (3.07) | 2 / 10 |
| GPT-6 Luna | 1.68 s (2.57) | 0.10 / 0.50 |
| GPT-6.1 Terra | 1.71 s (2.56) | 1 / 5 |

Haiku 5.5 is the default (cheapest, fast, warmest phrasing); Flash-Lite is the backup; Sol and
Luna are in the picker.

Voice: ElevenLabs **Flash v2.5** (their cheapest, lowest-latency streaming model) with the
"hanna" voice (`ELEVEN_VOICE_ID=4boNr3nCeZU6Yd1VGPvY`). The v3/v4 models go through the
text-to-dialogue API and aren't meant for realtime; v4 Turbo is a one-line switch
(`ELEVEN_MODEL=eleven_v4_turbo`). Fish Audio S2.1 Pro and Cartesia Sonic-3 on LiveKit Inference —
mini-kulu's voices — take over if the ElevenLabs key fails.

## Measured on the live server (EC2 t3.large, Singapore)

| Stage | Time |
|---|---|
| Villa joins → greeting starts | ~0.3–0.9 s (worker process prewarmed, init 1.9 s) |
| ElevenLabs time to first audio | 0.09–0.11 s ("Sarah"), 0.77 s ("hanna") |
| Simple question (tool + answer) | LLM 2.0 s first token, ~12.5k prompt tokens |
| "Plan a week in Ubud" | words after 3.4 s (filler), 3 Tripadvisor searches 1.0–1.3 s in parallel, itinerary on screen ~10 s, spoken summary at 11.4 s |
| Worker footprint | ~3 % CPU idle, ~340 MB RAM, image 2.6 GB |

The developer laptop (2012 dual-core i5) couldn't run the worker in real time next to Docker and
Chrome (voice-activity detection fell 16 s behind), which is why development moved to the server.

## Cost

**Extra AWS cost: none.** The worker is one more container on the existing on-demand t3.large
(same $0.1056/h while it runs, stopped otherwise). It only dials out, so no load balancer,
public port or security-group change. Audio between the box and LiveKit Cloud is tens of MB per
hour of calls (fractions of a cent of data transfer).

**LiveKit Cloud — Build (free) plan, project `villaops-ai`.** Free quota is shared across the
account's projects:

| Allowance | What it means for Villa |
|---|---|
| 1,000 agent session minutes / month (hard cap) | ~1,000 call minutes |
| 5 concurrent agent sessions | 5 simultaneous callers |
| 5,000 WebRTC participant minutes | caller + agent ≈ 2 per call minute → 2,500 call minutes |
| $2.50 inference credits | STT is $0.45/h → ~5 h of calls if nothing else uses it; the GPT-4.1 mini / Fish / Cartesia backups only bill when they serve a turn |
| 100 noise-cancellation minutes | `VOICE_NOISE_CANCELLATION=0` turns it off after that |
| End-of-turn model: development allowance for self-hosted agents | then falls back / bills $0.50 per 1k requests on paid plans |

**ElevenLabs.** Free tier: 10,000 credits/month per account; Flash v2.5 bills about half a credit
per character, so roughly 20k characters (~20 minutes of Villa speaking). The free tier has no
commercial licence, and two of the three free keys tried were disabled for "unusual activity"
within minutes, so a paid Starter plan is the safe choice for anything beyond a demo. If the key
stops working, the Inference voices keep the call going.

**OpenRouter (Claude Haiku 5.5).** Measured: a normal turn is ~12.5k prompt + ~0.5k output tokens
≈ $0.0015; an itinerary turn (3 LLM calls) ≈ $0.0055. A 5-minute call ≈ $0.01–0.02.

For a demo period this is effectively **$0 beyond the EC2 hours already budgeted.**

## Run it

On the demo server it's part of `docker-compose.prod.yml` (`./scripts/demo.sh deploy`).
Locally (needs a reasonably fast machine):

```bash
cd voice-agent
uv sync
uv run python agent.py dev          # registers the "villa" worker with LiveKit Cloud
uv run python test_caller.py "Plan a week in Ubud for two"   # typed test call via the backend
uv run pytest -q && uv run ruff check .
```

Environment (`.env` at the repo root): `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`,
`VOICE_AGENT_SECRET` (backend ↔ agent), `ELEVEN_API_KEY`, optional `ELEVEN_VOICE_ID`,
`ELEVEN_MODEL`, `VOICE_MODELS`, `VOICE_NOISE_CANCELLATION`; it reuses
`OPENROUTER_API_KEY`, `EXA_API_KEY` and the MCP URLs.
