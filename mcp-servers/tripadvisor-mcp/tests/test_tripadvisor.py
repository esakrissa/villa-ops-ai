"""Tests for the Tripadvisor MCP server — recorded Terra responses, no live requests."""

import json
from pathlib import Path
from typing import Any

import pytest

from tripadvisor_mcp import server
from tripadvisor_mcp.client import TripadvisorAPIError
from tripadvisor_mcp.formatters import format_place, photo_url, resolve_area

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text())


class FakeClient:
    def __init__(self, responses: dict[str, Any]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        self.calls.append((path, params or {}))
        response = self.responses[path]
        if isinstance(response, Exception):
            raise response
        return response


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch) -> FakeClient:
    nearby = load("locations_nearby.json")
    location = nearby["data"][1]["location"]
    photos = {"data": [nearby["data"][1]["photo"], nearby["data"][0]["photo"]]}
    client = FakeClient(
        {
            "/locations/nearby": nearby,
            "/locations/search": load("locations_search.json"),
            f"/locations/{location['id']}": location,
            f"/locations/{location['id']}/photos": photos,
        }
    )
    monkeypatch.setattr(server, "client", client)
    return client


async def test_nearby_by_area_returns_photo_cards(fake: FakeClient) -> None:
    result = await server.tripadvisor_search_nearby_locations(area="Ubud, Bali", max_results=3)

    assert "error" not in result
    assert result["kind"] == "places"
    assert result["source"] == "tripadvisor"
    place = result["results"][1]
    assert place["name"] == "Suan Bali Private Driver & Tour Guide"
    assert place["photo"].startswith("https://media-cdn.tripadvisor.com/media/photo-s/")
    assert place["rating"] == 5.0 and place["rating_scale"] == 5
    assert place["review_count"] == 73
    assert place["url"].startswith("https://www.tripadvisor.com/")
    assert place["subtitle"] == "Attraction"
    assert place["location"] == "Ubud"
    assert place["distance_km"] is not None

    path, params = fake.calls[0]
    assert path == "/locations/nearby"
    assert (params["lat"], params["lon"]) == (-8.5069, 115.2625)
    assert params["size"] == 3
    assert params["include_photo"] == "true"
    assert params["category"] == "ATTRACTION"
    assert params["min_rating"] == 3.0  # unrated places are dropped by default


async def test_nearby_accepts_plural_category_and_distance_sort(fake: FakeClient) -> None:
    await server.tripadvisor_search_nearby_locations(area="Canggu", category="Restaurants", sort_by="distance")
    _, params = fake.calls[0]
    assert params["category"] == "RESTAURANT"
    assert params["sort"] == "distance,asc"


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"area": "Atlantis"}, "Unknown area"),
        ({}, "Provide an area"),
        ({"area": "Ubud", "category": "spa"}, "category must be"),
        ({"area": "Ubud", "sort_by": "reviews"}, "sort_by"),
    ],
)
async def test_nearby_validation(fake: FakeClient, kwargs: dict[str, Any], message: str) -> None:
    result = await server.tripadvisor_search_nearby_locations(**kwargs)
    assert message in result["error"]
    assert fake.calls == []


async def test_search_locations(fake: FakeClient) -> None:
    result = await server.tripadvisor_search_locations("Ubud Monkey Forest", geo_name="Ubud", category="attraction")
    assert result["results"][0]["name"] == "Ubud Monkey Forest Silver Class"
    _, params = fake.calls[0]
    assert params["search_type"] == "COMBINED"


async def test_location_details_merges_photos(fake: FakeClient) -> None:
    result = await server.tripadvisor_get_location_details("13964849", max_photos=2)
    listing = result["listing"]
    assert result["kind"] == "listing_details"
    assert len(listing["photos"]) == 2
    assert listing["phone"] == "+62 819-9955-8457"
    assert listing["recommended_visit_hours"] == 4
    assert listing["photo_count"] == 49


async def test_location_details_404_mentions_allowlist(fake: FakeClient) -> None:
    fake.responses["/locations/999"] = TripadvisorAPIError("Tripadvisor API returned 404: Not Found", 404)
    result = await server.tripadvisor_get_location_details("999", max_photos=0)
    assert "allowlist" in result["error"]


async def test_api_errors_are_returned(fake: FakeClient) -> None:
    fake.responses["/locations/nearby"] = TripadvisorAPIError(
        "Tripadvisor API returned 403: API Key does not have access to endpoint", 403
    )
    result = await server.tripadvisor_search_nearby_locations(area="Ubud")
    assert "does not have access" in result["error"]
    assert result["results"] == []


def test_photo_url_uses_card_size() -> None:
    assert photo_url("photo-o/30/af/1b/0f/x.jpg") == "https://media-cdn.tripadvisor.com/media/photo-s/30/af/1b/0f/x.jpg"
    assert photo_url(None) is None


def test_resolve_area() -> None:
    assert resolve_area("Seminyak, Bali") == resolve_area("seminyak")
    assert resolve_area("Mars") is None


def test_format_place_handles_catalog_shape() -> None:
    entry = load("locations_search.json")["data"][0]
    place = format_place(entry)
    assert place["photo"] is None
    assert place["rating"] == 5.0
