"""Tests for the Booking.com MCP server — recorded API responses, no live requests."""

import json
from pathlib import Path
from typing import Any

import pytest

from booking_com_mcp import server
from booking_com_mcp.cache import JsonCache
from booking_com_mcp.client import BookingAPIError
from booking_com_mcp.formatters import format_hotel_details, pick_destination, price_summary, resize_photo

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text())


class FakeClient:
    """Stands in for BookingClient; serves fixtures by endpoint and records calls."""

    def __init__(self, responses: dict[str, Any]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def get(self, endpoint: str, params: dict[str, Any], ttl: int) -> Any:
        self.calls.append((endpoint, params))
        response = self.responses[endpoint]
        if isinstance(response, Exception):
            raise response
        return response


@pytest.fixture
def fake_client(monkeypatch: pytest.MonkeyPatch) -> FakeClient:
    fake = FakeClient(
        {
            "/api/v1/hotels/searchDestination": load("search_destination.json"),
            "/api/v1/hotels/searchHotels": load("search_hotels.json"),
            "/api/v1/hotels/getHotelDetails": load("hotel_details.json"),
        }
    )
    monkeypatch.setattr(server, "client", fake)
    return fake


async def test_search_hotels_returns_cards(fake_client: FakeClient) -> None:
    result = await server.booking_search_hotels("Ubud", "2026-12-10", "2026-12-13", currency="idr", max_results=3)

    assert "error" not in result
    assert result["kind"] == "listings"
    assert result["source"] == "booking.com"
    assert result["query"]["nights"] == 3
    assert result["query"]["currency"] == "IDR"
    assert len(result["results"]) == 3

    hotel = result["results"][1]
    assert hotel["name"] == "Arya Wellness - female only"
    assert hotel["rating"] == 9.4
    assert hotel["rating_scale"] == 10
    assert hotel["review_count"] == 1277
    assert hotel["photo"].startswith("https://cf.bstatic.com/xdata/images/hotel/max750/")
    assert hotel["price_per_night"] == pytest.approx(hotel["price_total"] / 3, abs=0.01)
    assert "highlighted_hotels=6048884" in hotel["url"]
    assert result["price_summary"]["min_per_night"] <= result["price_summary"]["max_per_night"]


async def test_search_uses_dest_id_not_city_ufi(fake_client: FakeClient) -> None:
    """The API now returns city_ufi=null; searching must use dest_id + search_type."""
    await server.booking_search_hotels("Ubud", "2026-12-10", "2026-12-13")

    endpoint, params = fake_client.calls[1]
    assert endpoint == "/api/v1/hotels/searchHotels"
    assert params["dest_id"] == "-2701757"
    assert params["search_type"] == "CITY"
    assert params["currency_code"] == "USD"
    assert params["sort_by"] == "popularity"


@pytest.mark.parametrize(
    ("checkin", "checkout", "message"),
    [
        ("2026-12-13", "2026-12-10", "after"),
        ("2026-12-01", "2027-02-01", "longer than"),
        ("12/10/2026", "2026-12-13", "Invalid isoformat"),
    ],
)
async def test_search_rejects_bad_dates(fake_client: FakeClient, checkin: str, checkout: str, message: str) -> None:
    result = await server.booking_search_hotels("Ubud", checkin, checkout)
    assert message in result["error"]
    assert result["results"] == []
    assert fake_client.calls == []


async def test_search_rejects_unknown_sort(fake_client: FakeClient) -> None:
    result = await server.booking_search_hotels("Ubud", "2026-12-10", "2026-12-13", sort_by="cheapest")
    assert "sort_by" in result["error"]


async def test_search_reports_api_errors(fake_client: FakeClient) -> None:
    fake_client.responses["/api/v1/hotels/searchDestination"] = BookingAPIError(
        "Booking.com API returned 403: You are not subscribed to this API."
    )
    result = await server.booking_search_hotels("Ubud", "2026-12-10", "2026-12-13")
    assert "not subscribed" in result["error"]
    assert result["results"] == []


async def test_search_unknown_destination(fake_client: FakeClient) -> None:
    fake_client.responses["/api/v1/hotels/searchDestination"] = []
    result = await server.booking_search_hotels("Atlantis", "2026-12-10", "2026-12-13")
    assert "No Booking.com destination" in result["error"]


async def test_hotel_details(fake_client: FakeClient) -> None:
    result = await server.booking_hotel_details("6048884", "2026-12-10", "2026-12-13")

    listing = result["listing"]
    assert result["kind"] == "listing_details"
    assert listing["url"] == "https://www.booking.com/hotel/id/arya-wellness-retreat.html"
    assert listing["currency"] == "USD"
    assert listing["price_per_night"] == pytest.approx(30.33, abs=0.01)
    assert listing["rating"] == 9.4
    assert "Free WiFi" in listing["facilities"]
    assert listing["photos"]
    assert listing["rooms"]
    assert all("<" not in info for info in listing["important_info"])


def test_pick_destination_skips_unusable_entries() -> None:
    assert pick_destination([{"name": "x"}, {"dest_id": "1", "search_type": "city"}]) == {
        "dest_id": "1",
        "search_type": "city",
    }
    assert pick_destination([]) is None


def test_price_summary() -> None:
    assert price_summary([{"price_per_night": 10}, {"price_per_night": 30}, {"price_per_night": None}]) == {
        "min_per_night": 10,
        "median_per_night": 20,
        "max_per_night": 30,
    }
    assert price_summary([]) is None


def test_resize_photo() -> None:
    url = "https://cf.bstatic.com/xdata/images/hotel/square500/1.jpg?k=abc&o="
    assert resize_photo(url) == "https://cf.bstatic.com/xdata/images/hotel/max750/1.jpg?k=abc&o="
    assert resize_photo(None) is None


def test_details_falls_back_to_total_over_nights() -> None:
    data = load("hotel_details.json")
    data["composite_price_breakdown"].pop("gross_amount_per_night")
    listing = format_hotel_details(data, checkin="2026-12-10", checkout="2026-12-13", nights=3)["listing"]
    assert listing["price_per_night"] == pytest.approx(listing["price_total"] / 3, abs=0.01)


async def test_cache_without_redis_is_a_no_op() -> None:
    cache = JsonCache(None, prefix="test")
    await cache.set("k", {"a": 1}, ttl=10)
    assert await cache.get("k") is None
    assert cache.key("search", {"b": 1, "a": 2}) == cache.key("search", {"a": 2, "b": 1})
