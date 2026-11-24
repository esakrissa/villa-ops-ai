"""Tests for the Airbnb MCP server — trimmed recorded pages, no live requests."""

from pathlib import Path
from typing import Any
from urllib.robotparser import RobotFileParser

import pytest

from airbnb_mcp import parsers, server
from airbnb_mcp.cache import JsonCache
from airbnb_mcp.scraper import AirbnbError, AirbnbScraper, extract_state

FIXTURES = Path(__file__).parent / "fixtures"


def page(name: str) -> str:
    return (FIXTURES / name).read_text()


class FakeScraper:
    """Serves fixture pages by path prefix and records requests."""

    ignore_robots_txt = True

    def __init__(self, pages: dict[str, str]) -> None:
        self.pages = pages
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def fetch_state(self, path: str, params: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        self.calls.append((path, params))
        for prefix, html in self.pages.items():
            if path.startswith(prefix):
                return f"https://www.airbnb.com{path}", extract_state(html)
        raise AirbnbError(f"no fixture for {path}")


class MemoryCache(JsonCache):
    def __init__(self) -> None:
        super().__init__(None, prefix="test")
        self.store: dict[str, Any] = {}

    async def get(self, key: str) -> Any | None:
        return self.store.get(key)

    async def set(self, key: str, value: Any, ttl: int) -> None:
        self.store[key] = value


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch) -> FakeScraper:
    scraper = FakeScraper({"/s/": page("search_canggu_usd.html"), "/rooms/": page("listing.html")})
    monkeypatch.setattr(server, "scraper", scraper)
    monkeypatch.setattr(server, "cache", MemoryCache())
    return scraper


async def test_search_returns_cards_in_usd(fake: FakeScraper) -> None:
    result = await server.airbnb_search("Canggu, Bali", "2026-12-10", "2026-12-13", max_results=3)

    assert "error" not in result
    assert result["kind"] == "listings"
    assert result["source"] == "airbnb"
    assert len(result["results"]) == 3
    assert result["query"]["nights"] == 3

    first = result["results"][0]
    assert first["currency"] == "USD"
    assert first["id"].isdigit()
    assert first["url"].startswith(f"https://www.airbnb.com/rooms/{first['id']}?check_in=2026-12-10")
    assert first["photo"].startswith("https://a0.muscache.com/") and first["photo"].endswith("?im_w=720")
    assert first["rating_scale"] == 5
    assert first["price_per_night"] == pytest.approx(first["price_total"] / 3, abs=0.01)

    path, params = fake.calls[0]
    assert path == "/s/Canggu%2C%20Bali/homes"
    assert params["currency"] == "USD"


async def test_search_is_cached(fake: FakeScraper) -> None:
    await server.airbnb_search("Canggu, Bali", "2026-12-10", "2026-12-13", max_results=2)
    again = await server.airbnb_search("canggu, bali ", "2026-12-10", "2026-12-13", max_results=4)
    assert len(fake.calls) == 1
    assert len(again["results"]) == 4


async def test_search_parses_idr_and_discounts() -> None:
    state = extract_state(page("search_ubud_idr.html"))
    listings = parsers.search_results(state, checkin="2026-12-10", checkout="2026-12-13", adults=2, currency="IDR")
    discounted = next(r for r in listings if r["original_price_total"])
    assert discounted["original_price_total"] > discounted["price_total"]
    rated = next(r for r in listings if r["rating"])
    assert 0 < rated["rating"] <= 5 and rated["review_count"] > 0


@pytest.mark.parametrize(
    ("checkin", "checkout", "message"),
    [("2026-12-10", None, "both"), ("2026-12-13", "2026-12-10", "after"), ("2026-12-01", "2027-02-01", "longer")],
)
async def test_search_rejects_bad_dates(fake: FakeScraper, checkin: str, checkout: str | None, message: str) -> None:
    result = await server.airbnb_search("Ubud", checkin, checkout)
    assert message in result["error"]
    assert fake.calls == []


async def test_search_reports_scraper_errors(fake: FakeScraper) -> None:
    fake.pages.clear()
    result = await server.airbnb_search("Ubud")
    assert result["error"].startswith("no fixture")
    assert result["results"] == []


async def test_listing_details(fake: FakeScraper) -> None:
    result = await server.airbnb_listing_details("1288193758385508971", "2026-12-10", "2026-12-13")

    listing = result["listing"]
    assert result["kind"] == "listing_details"
    assert listing["name"] == "Exclusive Jungle Villa with Waterfall View"
    assert listing["rating"] == 4.97
    assert listing["review_count"] == 37
    assert listing["badge"] == "Guest favorite"
    assert listing["host"]["is_superhost"] is True
    assert "Kitchen" in listing["amenities"]
    assert listing["photos"] and all(p.endswith("?im_w=720") for p in listing["photos"])
    assert listing["description"] and "<" not in listing["description"]
    assert listing["overview"] == ["2 guests", "1 bedroom", "1 bed", "1 bath"]


async def test_listing_details_rejects_non_numeric_id(fake: FakeScraper) -> None:
    result = await server.airbnb_listing_details("Exclusive Jungle Villa")
    assert "numeric" in result["error"]
    assert fake.calls == []


@pytest.mark.parametrize(
    ("text", "expected"),
    [("$1,234", 1234.0), ("Rp\xa01,597,000", 1597000.0), ("€99.50", 99.5), ("", None), (None, None)],
)
def test_parse_price(text: str | None, expected: float | None) -> None:
    assert parsers.parse_price(text) == expected


def test_parse_rating() -> None:
    assert parsers.parse_rating("4.97 (37)") == (4.97, 37, None)
    assert parsers.parse_rating("4.9 (1,204)") == (4.9, 1204, None)
    assert parsers.parse_rating("New") == (None, 0, "New")


def test_nights_from_qualifier() -> None:
    assert parsers.nights_from_qualifier("for 3 nights") == 3
    assert parsers.nights_from_qualifier("night") == 1
    assert parsers.nights_from_qualifier(None) is None


def test_extract_state_rejects_unknown_pages() -> None:
    with pytest.raises(AirbnbError):
        extract_state("<html>captcha</html>")


async def test_robots_txt_is_respected_by_default() -> None:
    robots = RobotFileParser()
    robots.parse(["User-agent: *", "Disallow: /s/"])
    scraper = AirbnbScraper(ignore_robots_txt=False)
    scraper._robots = robots  # skip the network fetch of robots.txt

    with pytest.raises(AirbnbError, match=r"robots\.txt"):
        await scraper.fetch_state("/s/Ubud/homes", {})


async def test_search_entire_home_filter(fake: FakeScraper) -> None:
    await server.airbnb_search("Ubud", "2026-12-10", "2026-12-13", adults=4, entire_home_only=True, min_bedrooms=2)
    _, params = fake.calls[0]
    assert params["room_types[]"] == "Entire home/apt"
    assert params["min_bedrooms"] == 2
    assert params["adults"] == 4


async def test_search_without_filters_sends_no_room_type(fake: FakeScraper) -> None:
    await server.airbnb_search("Ubud")
    _, params = fake.calls[0]
    assert params["room_types[]"] is None and params["min_bedrooms"] is None
