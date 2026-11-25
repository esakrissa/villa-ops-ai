"""``show_itinerary``: put a day-by-day trip plan on the caller's screen.

A week in Ubud is too long to listen to. The model builds the plan from what the search tools
returned, calls this tool with it, and then says a two-sentence summary. The page draws the plan
as a card (the same card shows up later in the text chat, from the saved transcript).
"""

import json
from typing import Any

from livekit.agents import RunContext, function_tool, llm

from villa.mcp_tools import EventSink, ToolResults, ToolTrace

MAX_DAYS = 14

SCHEMA: dict[str, Any] = {
    "name": "show_itinerary",
    "description": (
        "Show a day-by-day travel itinerary on the user's screen. Use it whenever you plan a trip "
        "(e.g. a week in Ubud). Fill every day. Keep each slot to one short sentence naming real "
        "places from your searches. After calling it, speak only a short summary."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "e.g. 'A relaxed week in Ubud'"},
            "summary": {"type": "string", "description": "One or two sentences about the trip's style"},
            "stay": {"type": "string", "description": "Suggested hotel or villa and area, with price if known"},
            "days": {
                "type": "array",
                "description": "One entry per day, in order",
                "items": {
                    "type": "object",
                    "properties": {
                        "day": {"type": "integer"},
                        "title": {"type": "string", "description": "Theme of the day, e.g. 'Rice terraces & temples'"},
                        "morning": {"type": "string"},
                        "afternoon": {"type": "string"},
                        "evening": {"type": "string"},
                        "food": {"type": "string", "description": "Where to eat that day"},
                    },
                    "required": ["day", "title", "morning", "afternoon", "evening"],
                },
            },
            "tips": {"type": "array", "items": {"type": "string"}, "description": "Up to 4 practical tips"},
        },
        "required": ["title", "days"],
    },
}


def normalize(args: dict[str, Any]) -> dict[str, Any]:
    """Keep the fields the card draws, with sane sizes."""
    days = []
    for i, d in enumerate((args.get("days") or [])[:MAX_DAYS]):
        if not isinstance(d, dict):
            continue
        days.append(
            {
                "day": int(d.get("day") or i + 1),
                **{k: str(d[k]).strip() for k in ("title", "morning", "afternoon", "evening", "food") if d.get(k)},
            }
        )
    tips = [str(t).strip() for t in (args.get("tips") or [])[:4] if str(t).strip()]
    return {
        "kind": "itinerary",
        "title": str(args.get("title") or "Your itinerary").strip(),
        "summary": str(args.get("summary") or "").strip(),
        "stay": str(args.get("stay") or "").strip(),
        "days": days,
        "tips": tips,
    }


def itinerary_tool(on_event: EventSink | None, results: ToolResults) -> llm.RawFunctionTool:
    async def show_itinerary(raw_arguments: dict[str, object], context: RunContext) -> str:
        call_id = context.function_call.call_id
        plan = normalize(dict(raw_arguments))
        trace = ToolTrace(on_event, call_id, "show_itinerary", "villa", {"title": plan["title"]})
        if not plan["days"]:
            trace.fail("no days in the plan")
            return "The itinerary had no days. Build the days first, then call show_itinerary again."
        text = json.dumps(plan)
        trace.ok(text)
        results.put(call_id, text)
        return (
            f"The {len(plan['days'])}-day itinerary is now on the user's screen. Give a short spoken "
            "summary (two or three sentences, a highlight or two) and ask if they'd like any changes."
        )

    return function_tool(show_itinerary, raw_schema=SCHEMA)
