"""Villa: the realtime voice agent of VillaOps AI.

Browser ⇄ LiveKit Cloud (WebRTC) ⇄ this worker: speech-to-text → LLM with the VillaOps MCP tools →
ElevenLabs voice. The backend issues the LiveKit token (POST /api/v1/voice/session); joining the
room dispatches this agent with signed metadata (user id, conversation, model, tools switched off).

The worker only dials out (to LiveKit, OpenRouter, ElevenLabs, the MCP servers and the backend),
so it needs no public port: on the demo EC2 box it's one more docker-compose service.

    uv run python agent.py dev      # local worker, registers with LiveKit Cloud
    uv run python agent.py start    # production mode (Docker)
"""

import asyncio
import json
import logging
import os

from livekit import agents
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    ErrorEvent,
    TurnHandlingOptions,
    inference,
    llm,
    room_io,
)
from livekit.agents.voice.agent_session import SessionConnectOptions
from livekit.agents.voice.events import ConversationItemAddedEvent, FunctionToolsExecutedEvent

# Plugins register on the main thread, before job processes start
from livekit.plugins import ai_coustics

from villa import models
from villa.backend import Backend
from villa.itinerary import itinerary_tool
from villa.mcp_tools import ToolResults, build_tools, discover, exa_url, tool_event_json
from villa.prompt import greeting, instructions
from villa.settings import settings

# The end-of-turn model runs on LiveKit Inference, so nothing local needs preloading (saves RAM)
os.environ.setdefault("LIVEKIT_AGENTS_PRELOAD_LOCAL_INFERENCE", "0")

logger = logging.getLogger("villa")

# Tool calls as they happen, for the page (frontend VoiceMode reads this text-stream topic)
TOOL_EVENTS_TOPIC = "villa.tool"
APOLOGY = "Sorry, I lost my train of thought there. Could you say that again?"


def mcp_sources() -> list[tuple[str, str]]:
    sources = list(settings.mcp_sources)
    if settings.exa_api_key:
        sources.append(("exa", exa_url(settings.exa_api_key)))
    return sources


def prewarm(_proc: agents.JobProcess) -> None:
    """Load the tool lists while the process is idle, so a call doesn't wait for discovery."""
    try:
        asyncio.run(discover(mcp_sources()))
    except Exception:
        logger.exception("tool discovery during prewarm failed (will retry per call)")


server = AgentServer(
    setup_fnc=prewarm,
    num_idle_processes=int(os.getenv("VOICE_IDLE_PROCESSES", "1")),
    initialize_process_timeout=60,
)


def first_name(name: str | None) -> str | None:
    return name.split()[0] if name and name.strip() else None


@server.rtc_session(agent_name=settings.agent_name)
async def entrypoint(ctx: agents.JobContext) -> None:
    meta = json.loads(ctx.job.metadata or "{}")
    user_id = meta.get("user_id")
    conversation_id = meta.get("conversation_id")
    if not user_id or not conversation_id:
        logger.error("dispatch without user/conversation metadata; leaving room %s", ctx.room.name)
        ctx.shutdown("missing metadata")
        return
    model = meta.get("model") or settings.default_model
    user_name = meta.get("user_name")
    disabled = set(meta.get("disabled_tools") or [])
    logger.info("call: room=%s user=%s conversation=%s model=%s", ctx.room.name, user_id, conversation_id, model)

    backend = Backend(settings.backend_url, settings.agent_secret, user_id, conversation_id, model)
    ctx.add_shutdown_callback(backend.aclose)
    results = ToolResults()

    # One sender in order, so a tool's "ok" never overtakes its "running" on the way to the page
    events: asyncio.Queue[dict] = asyncio.Queue()

    async def send_events() -> None:
        while True:
            event = await events.get()
            if not ctx.room.isconnected():
                continue
            try:
                await ctx.room.local_participant.send_text(tool_event_json(event), topic=TOOL_EVENTS_TOPIC)
            except Exception as e:
                logger.warning("tool event not sent: %r", e)

    sender = asyncio.create_task(send_events(), name="villa-tool-events")

    async def stop_sender() -> None:
        sender.cancel()

    ctx.add_shutdown_callback(stop_sender)

    def send_event(event: dict) -> None:
        events.put_nowait(event)

    specs, (_title, history) = await asyncio.gather(discover(mcp_sources()), backend.history())
    tools = build_tools(
        specs,
        user_id=user_id,
        disabled=disabled,
        timeout_s=settings.tool_timeout_s,
        on_event=send_event,
        results=results,
        max_web_searches=settings.max_web_searches,
    )
    tools.append(itinerary_tool(send_event, results))
    logger.info("%d tools: %s", len(tools), [t.info.name for t in tools])

    chat_ctx = llm.ChatContext()
    for m in history:
        chat_ctx.add_message(role="user" if m["role"] == "user" else "assistant", content=m["content"])

    session = AgentSession(
        stt=models.stt(),
        llm=models.llm_chain(settings, model),
        tts=models.tts_chain(settings),
        turn_handling=TurnHandlingOptions(
            turn_detection=inference.TurnDetector(version="v1", local_fallback=False),
        ),
        conn_options=SessionConnectOptions(
            llm_conn_options=models.LLM_CONN_OPTIONS,
            tts_conn_options=models.tts_conn_options(settings.tts_timeout_s),
        ),
        # Itineraries take a few steps: attractions + restaurants (+ hotels), then show_itinerary
        max_tool_steps=6,
    )

    # ---- transcript → backend (the call becomes a chat conversation) ----
    @session.on("conversation_item_added")
    def _on_item(ev: ConversationItemAddedEvent) -> None:
        item = ev.item
        if not isinstance(item, llm.ChatMessage):
            return
        text = (item.text_content or "").strip()
        if not text:
            return
        if item.role == "user":
            backend.user(text)
        elif item.role == "assistant":
            backend.assistant(text)

    @session.on("function_tools_executed")
    def _on_tools(ev: FunctionToolsExecutedEvent) -> None:
        calls = []
        for fc in ev.function_calls:
            try:
                args = json.loads(fc.arguments or "{}")
            except ValueError:
                args = {"raw": fc.arguments}
            calls.append({"id": fc.call_id, "name": fc.name, "args": args})
        outs = [(o.call_id, results.pop(o.call_id, o.output)) for o in ev.function_call_outputs]
        if calls:
            backend.tool_step(calls, outs)

    @session.on("agent_state_changed")
    def _on_state(ev) -> None:
        logger.info("agent state %s -> %s", ev.old_state, ev.new_state)

    @session.on("metrics_collected")
    def _on_metrics(ev) -> None:
        m = ev.metrics
        kind = type(m).__name__
        if kind == "LLMMetrics":
            logger.info(
                "llm ttft %.2fs total %.2fs tokens %s/%s", m.ttft, m.duration, m.prompt_tokens, m.completion_tokens
            )
        elif kind == "TTSMetrics":
            logger.info("tts ttfb %.2fs (%s)", m.ttfb, getattr(m, "label", ""))

    # If every model fails a turn, say so instead of going silent
    @session.on("error")
    def _on_error(ev: ErrorEvent) -> None:
        err = ev.error
        if getattr(err, "type", None) == "llm_error" and not getattr(err, "recoverable", True):
            logger.warning("LLM turn failed on every model")
            try:
                session.say(APOLOGY, add_to_chat_ctx=False)
            except RuntimeError:
                pass

    noise_cancellation = (
        ai_coustics.audio_enhancement(model=ai_coustics.EnhancerModel.QUAIL_VF_S)
        if settings.noise_cancellation
        else None
    )

    await session.start(
        room=ctx.room,
        agent=Agent(instructions=instructions(user_name, sorted(disabled)), tools=tools, chat_ctx=chat_ctx),
        record={"audio": False},
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(noise_cancellation=noise_cancellation),
        ),
    )
    session.say(greeting(first_name(user_name), continuing=bool(history)))


if __name__ == "__main__":
    agents.cli.run_app(server)
