"""Unit tests for Villa's tool bridge, result compaction, itinerary and transcript buffering."""

import asyncio
import json

from villa.backend import Backend
from villa.itinerary import normalize
from villa.mcp_tools import FillerGate, ToolResults, for_model, tool_parameters
from villa.prompt import greeting, instructions


def test_user_id_is_hidden_from_the_model():
    schema = {
        "type": "object",
        "title": "booking_searchArguments",
        "properties": {
            "guest_name": {"type": "string", "title": "Guest Name"},
            "user_id": {"anyOf": [{"type": "string"}, {"type": "null"}], "title": "User Id"},
        },
        "required": ["guest_name", "user_id"],
    }
    params, takes_user_id = tool_parameters(schema)
    assert takes_user_id is True
    assert "user_id" not in params["properties"]
    assert params["required"] == ["guest_name"]
    assert "title" not in json.dumps(params)


def test_tools_without_user_id_are_left_alone():
    params, takes_user_id = tool_parameters({"type": "object", "properties": {"area": {"type": "string"}}})
    assert takes_user_id is False
    assert params == {"type": "object", "properties": {"area": {"type": "string"}}}


def test_market_results_are_compacted_for_the_model():
    raw = {
        "source": "tripadvisor",
        "kind": "places",
        "total_found": 900,
        "query": {"area": "Ubud"},
        "results": [
            {
                "id": "1",
                "name": "Campuhan Ridge Walk",
                "rating": 4.5,
                "review_count": 12000,
                "photo": "https://media/x.jpg",
                "photos": ["https://media/x.jpg"],
                "url": "https://tripadvisor/x",
                "latitude": -8.5,
                "description": "A" * 500,
            }
        ],
    }
    text = for_model(json.dumps(raw), 6000)
    data = json.loads(text)
    row = data["results"][0]
    assert row["name"] == "Campuhan Ridge Walk" and row["rating"] == 4.5
    assert "photo" not in row and "url" not in row and "latitude" not in row
    assert len(row["description"]) == 140
    assert len(text) < len(json.dumps(raw)) / 2


def test_other_results_are_only_clipped():
    assert for_model("plain text", 100) == "plain text"
    assert for_model("x" * 50, 10).startswith("x" * 10)
    assert for_model('{"bookings": []}', 100) == '{"bookings": []}'


def test_filler_gate_allows_one_filler_per_window():
    gate = FillerGate(every_s=60)
    assert gate.take() is True
    assert gate.take() is False


def test_itinerary_is_normalized():
    plan = normalize(
        {
            "title": " A week in Ubud ",
            "days": [{"title": "Arrive", "morning": "Land", "afternoon": "Check in", "evening": "Dinner"}] * 20,
            "tips": ["a", "", "b", "c", "d", "e"],
        }
    )
    assert plan["kind"] == "itinerary"
    assert plan["title"] == "A week in Ubud"
    assert len(plan["days"]) == 14
    assert plan["days"][1]["day"] == 2
    assert plan["tips"] == ["a", "b", "c"]  # first four, empty ones dropped


def test_tool_results_pop_falls_back():
    r = ToolResults()
    r.put("c1", "full")
    assert r.pop("c1", "short") == "full"
    assert r.pop("c1", "short") == "short"


def test_prompt_and_greeting():
    text = instructions("Esa Krissa", ["send_notification"])
    assert "Esa Krissa" in text and "send_notification" in text
    assert greeting("Esa", continuing=False).startswith("Hi Esa, I'm Villa")
    assert "conversation" in greeting(None, continuing=True)


async def test_greeting_waits_for_the_first_user_turn():
    backend = Backend("http://backend.invalid", "s", "u", "c", "m")
    sent: list = []
    backend._queue.put_nowait = sent.append  # type: ignore[method-assign]
    backend.assistant("Hi, I'm Villa")
    assert sent == []  # held: nobody has spoken yet
    backend.user("Plan a week in Ubud")
    assert [m["role"] for batch in sent for m in batch] == ["assistant", "user"]
    backend.assistant("Sure")
    assert len(sent) == 3
    backend._worker.cancel()
    await asyncio.gather(backend._worker, return_exceptions=True)
    await backend._client.aclose()
