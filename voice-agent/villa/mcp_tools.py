"""VillaOps MCP tools as LiveKit function tools, with the user pinned server-side.

The text agent (backend/app/agent) reaches the same MCP servers: the VillaOps server (properties,
bookings, guests, analytics, notifications, knowledge base), the Booking.com / Airbnb / Tripadvisor
servers in mcp-servers/, and Exa's hosted web search. Here each MCP tool becomes a LiveKit
``RawFunctionTool`` whose schema is the MCP input schema with ``user_id`` removed:

- The model never sees or chooses ``user_id``. The tool injects it from the LiveKit dispatch
  metadata, which only the backend can sign, so a caller can't reach another user's data by
  asking for it (the text agent passes it through the prompt instead).
- Destructive tools (deletes) are not offered by voice: they need the confirmation card of the
  text chat.
- Every call has a deadline, its result is clipped for the model, and the page is told about it as
  it happens (running → ok / error), with the full result so it can draw the same cards as the chat.

Tool discovery costs ~1 s locally (Exa's hosted server ~2.5 s), so lists are cached per process
and warmed when the worker process starts.
"""

import asyncio
import json
import logging
import random
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from livekit.agents import RunContext, function_tool, llm
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

logger = logging.getLogger("villa.tools")

DESTRUCTIVE_TOOLS = frozenset({"property_delete", "guest_delete"})
# From Exa's server only the search tool: page fetches are slow and long for a voice turn
EXA_TOOLS = frozenset({"web_search_exa"})
EXA_MCP_URL = "https://mcp.exa.ai/mcp"

LIST_TIMEOUT_S = 6.0
CACHE_TTL_S = 600.0
# What the model reads of a result (it reads all of it before its next first token)
MAX_RESULT_CHARS = 6_000
MAX_SEARCH_CHARS = 3_000
# What the page gets (listing cards need the whole JSON)
MAX_EVENT_CHARS = 60_000

FILLERS = (
    "One moment, let me check.",
    "Let me look that up for you.",
    "Just a second, I'm checking.",
    "Give me a moment.",
)
FILLER_DELAY_S = 0.8

# Booking.com's RapidAPI search can take 20+ s on a cold query (cached 6 h after that); a caller
# won't wait that long, so it gets less time than the default and the model says it couldn't check.
SOURCE_TIMEOUTS_S = {"booking": 12.0, "airbnb": 12.0, "exa": 8.0}

EventSink = Callable[[dict[str, Any]], None]


@dataclass(frozen=True)
class ToolSpec:
    source: str
    url: str
    name: str
    description: str
    parameters: dict[str, Any]
    takes_user_id: bool


def clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit] + "\n…[cut off]"


# Fields of a market search result (Booking.com / Airbnb / Tripadvisor) the model needs to talk
# about it; photos, URLs and coordinates are for the page's cards only.
LISTING_FIELDS = (
    "id",
    "name",
    "subtitle",
    "rating",
    "rating_scale",
    "review_count",
    "price_per_night",
    "price_total",
    "price",
    "currency",
    "location",
    "distance_km",
    "badge",
)


def for_model(text: str, limit: int) -> str:
    """What the model reads of a tool result.

    Market searches return several KB of JSON per call (photos, URLs, coordinates); the model
    reads all of it before its next first token, and an itinerary turn makes two or three of
    them. Those are cut down to the fields worth saying; everything else is just clipped.
    """
    try:
        data = json.loads(text)
    except ValueError:
        return clip(text, limit)
    if isinstance(data, dict) and data.get("kind") in ("places", "listings") and isinstance(data.get("results"), list):
        rows = []
        for r in data["results"]:
            if not isinstance(r, dict):
                continue
            row = {k: r[k] for k in LISTING_FIELDS if r.get(k) not in (None, "", [])}
            if r.get("description"):
                row["description"] = str(r["description"])[:140]
            rows.append(row)
        compact = {k: data[k] for k in ("source", "kind", "total_found", "price_summary") if data.get(k) is not None}
        compact["results"] = rows
        compact["note"] = "Shown to the user as photo cards."
        return clip(json.dumps(compact, separators=(",", ":"), ensure_ascii=False), limit)
    return clip(text, limit)


def _strip_titles(schema: Any) -> Any:
    """Drop JSON-schema ``title`` keys (tokens the model doesn't need); keep everything else."""
    if isinstance(schema, dict):
        return {k: _strip_titles(v) for k, v in schema.items() if k != "title"}
    if isinstance(schema, list):
        return [_strip_titles(v) for v in schema]
    return schema


def tool_parameters(input_schema: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """The schema the model sees (no ``user_id``) and whether the tool takes ``user_id``."""
    schema = _strip_titles(input_schema or {})
    props = dict(schema.get("properties") or {})
    takes_user_id = props.pop("user_id", None) is not None
    params: dict[str, Any] = {"type": "object", "properties": props}
    required = [r for r in schema.get("required") or [] if r != "user_id"]
    if required:
        params["required"] = required
    return params, takes_user_id


def exa_url(api_key: str) -> str:
    return f"{EXA_MCP_URL}?exaApiKey={api_key}"


async def _list_source(source: str, url: str) -> list[ToolSpec]:
    async with asyncio.timeout(LIST_TIMEOUT_S):
        async with streamable_http_client(url) as (read, write), ClientSession(read, write) as session:
            await session.initialize()
            listed = await session.list_tools()
    specs = []
    for tool in listed.tools:
        if tool.name in DESTRUCTIVE_TOOLS or (source == "exa" and tool.name not in EXA_TOOLS):
            continue
        params, takes_user_id = tool_parameters(tool.input_schema)
        specs.append(
            ToolSpec(
                source=source,
                url=url,
                name=tool.name,
                description=(tool.description or tool.name).strip()[:1500],
                parameters=params,
                takes_user_id=takes_user_id,
            )
        )
    return specs


_cache: dict[str, tuple[float, list[ToolSpec]]] = {}


async def discover(sources: list[tuple[str, str]]) -> list[ToolSpec]:
    """Every tool of every reachable source (cached per URL; an unreachable source is skipped)."""

    async def one(source: str, url: str) -> list[ToolSpec]:
        hit = _cache.get(url)
        if hit and time.monotonic() - hit[0] < CACHE_TTL_S:
            return hit[1]
        specs = await _list_source(source, url)
        _cache[url] = (time.monotonic(), specs)
        logger.info("loaded %d tools from %s", len(specs), source)
        return specs

    results = await asyncio.gather(*(one(s, u) for s, u in sources), return_exceptions=True)
    tools: list[ToolSpec] = []
    for (source, _url), result in zip(sources, results, strict=True):
        if isinstance(result, BaseException):
            logger.warning("MCP source %s unavailable: %r", source, result)
            continue
        tools.extend(result)
    return tools


async def call_mcp(url: str, name: str, args: dict[str, Any], timeout_s: float) -> str:
    """Call one MCP tool on a fresh connection (the servers are stateless HTTP)."""
    async with asyncio.timeout(timeout_s):
        async with streamable_http_client(url) as (read, write), ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(name, args)
    parts = [getattr(c, "text", "") for c in result.content if getattr(c, "type", None) == "text"]
    text = "\n".join(p for p in parts if p)
    if result.is_error:
        raise RuntimeError(text or f"{name} failed")
    return text


class ToolTrace:
    """One tool call as the page sees it: ``running`` now, then ``ok`` or ``error``.

    Events share the LLM's call id, so the page updates one card. A broken sink never breaks
    the call.
    """

    def __init__(self, sink: EventSink | None, call_id: str, spec_name: str, source: str, args: dict) -> None:
        self._sink = sink
        self._start = time.perf_counter()
        self._base = {"id": call_id, "name": spec_name, "source": source, "args": args}
        self._emit("running")

    @property
    def seconds(self) -> float:
        return round(time.perf_counter() - self._start, 3)

    def ok(self, result: str) -> None:
        self._emit("ok", result=clip(result, MAX_EVENT_CHARS), seconds=self.seconds)

    def fail(self, error: str) -> None:
        self._emit("error", error=error, seconds=self.seconds)

    def _emit(self, status: str, **fields: Any) -> None:
        if self._sink is None:
            return
        try:
            self._sink({**self._base, "status": status, **fields})
        except Exception:
            logger.exception("failed to report a tool event")


class ToolResults:
    """Full results by call id, for the transcript (the model only reads a clipped version)."""

    def __init__(self) -> None:
        self._by_call: dict[str, str] = {}

    def put(self, call_id: str, result: str) -> None:
        self._by_call[call_id] = result

    def pop(self, call_id: str, default: str) -> str:
        return self._by_call.pop(call_id, default)


class FillerGate:
    """At most one filler line every ``every_s`` seconds.

    Several tools run in one turn (an itinerary searches attractions, restaurants and stays in
    parallel, then maybe more); without a gate each one said "one moment" and the caller heard
    four in a row.
    """

    def __init__(self, every_s: float = 12.0) -> None:
        self.every_s = every_s
        self._last = -1e9

    def take(self) -> bool:
        now = time.monotonic()
        if now - self._last < self.every_s:
            return False
        self._last = now
        return True


def _filler(context: RunContext, gate: FillerGate) -> Callable[[int], Any]:
    # Kept out of the chat history: the model took the line as its own and then waited
    def say(_step: int) -> Any:
        if not gate.take():
            return None
        return context.session.say(random.choice(FILLERS), add_to_chat_ctx=False)

    return say


def build_tool(
    spec: ToolSpec,
    *,
    user_id: str,
    timeout_s: float,
    on_event: EventSink | None,
    results: ToolResults,
    gate: FillerGate,
    budget: dict[str, int] | None = None,
) -> llm.RawFunctionTool:
    """A LiveKit tool that calls ``spec`` with ``user_id`` pinned."""
    max_chars = MAX_SEARCH_CHARS if spec.source == "exa" else MAX_RESULT_CHARS
    timeout_s = SOURCE_TIMEOUTS_S.get(spec.source, timeout_s)

    async def handler(raw_arguments: dict[str, object], context: RunContext) -> str:
        call_id = context.function_call.call_id
        args = {k: v for k, v in raw_arguments.items() if v is not None and k != "user_id"}
        trace = ToolTrace(on_event, call_id, spec.name, spec.source, args)
        if budget is not None and spec.name in budget:
            if budget[spec.name] <= 0:
                trace.fail("limit reached for this call")
                return "You've used all the web searches allowed in one call. Answer from what you know."
            budget[spec.name] -= 1
        call_args = {**args, "user_id": user_id} if spec.takes_user_id else args
        try:
            async with context.with_filler(_filler(context, gate), delay=FILLER_DELAY_S):
                text = await call_mcp(spec.url, spec.name, call_args, timeout_s)
        except TimeoutError:
            logger.warning("%s timed out after %.0f s", spec.name, timeout_s)
            trace.fail(f"no answer within {timeout_s:g} s")
            results.put(call_id, f"Error: {spec.name} timed out")
            return f"{spec.name} didn't answer in time. Say you couldn't check just now."
        except Exception as e:
            logger.warning("%s failed: %r", spec.name, e)
            trace.fail(f"{type(e).__name__}: {e}"[:300])
            results.put(call_id, f"Error: {e}")
            return f"{spec.name} failed: {e}. Tell the user briefly and carry on."
        logger.info("%s ok in %.2f s (%d chars)", spec.name, trace.seconds, len(text))
        trace.ok(text)
        results.put(call_id, text)
        return for_model(text, max_chars) if text else "No results."

    return function_tool(
        handler,
        raw_schema={"name": spec.name, "description": spec.description, "parameters": spec.parameters},
    )


def build_tools(
    specs: list[ToolSpec],
    *,
    user_id: str,
    disabled: set[str],
    timeout_s: float,
    on_event: EventSink | None,
    results: ToolResults,
    max_web_searches: int,
) -> list[llm.RawFunctionTool]:
    budget = {name: max_web_searches for name in EXA_TOOLS}
    gate = FillerGate()
    return [
        build_tool(
            spec,
            user_id=user_id,
            timeout_s=timeout_s,
            on_event=on_event,
            results=results,
            gate=gate,
            budget=budget,
        )
        for spec in specs
        if spec.name not in disabled
    ]


def tool_event_json(event: dict[str, Any]) -> str:
    return json.dumps(event, default=str)
