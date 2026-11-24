"""Airbnb MCP server — Streamable HTTP on port 8003.

Tools (same names as openbnb's mcp-server-airbnb):
    airbnb_search            — listings for a location with photos, ratings and prices
    airbnb_listing_details   — description, amenities, house rules, host and photos for one listing

No API key needed; pages are fetched from airbnb.com and cached in Redis.
Search pages are disallowed by Airbnb's robots.txt, so ``airbnb_search`` only
works with ``AIRBNB_IGNORE_ROBOTS_TXT=true`` (same opt-in as the original
server's ``--ignore-robots-txt`` flag).
"""

import contextlib
import logging
import os
from datetime import date
from typing import Any
from urllib.parse import quote

import uvicorn
from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from mcp_types import ToolAnnotations
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

from airbnb_mcp.cache import JsonCache
from airbnb_mcp.parsers import SOURCE, format_listing, format_search, search_results
from airbnb_mcp.scraper import AirbnbError, AirbnbScraper

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("airbnb-mcp")

PORT = int(os.getenv("PORT", "8003"))
SEARCH_TTL = int(os.getenv("AIRBNB_CACHE_TTL", str(6 * 3600)))
DETAILS_TTL = 24 * 3600
MAX_NIGHTS = 30

scraper = AirbnbScraper(ignore_robots_txt=os.getenv("AIRBNB_IGNORE_ROBOTS_TXT", "false").lower() == "true")
cache = JsonCache(os.getenv("REDIS_URL"), prefix="mcp:airbnb")

mcp = MCPServer(
    name="airbnb-mcp",
    instructions=(
        "Live Airbnb data for market research: search stays in a location with photos, ratings "
        "and prices, then fetch details for a specific listing."
    ),
)

READ_ONLY = ToolAnnotations(read_only_hint=True, open_world_hint=True)


def _error(message: str, **extra: Any) -> dict[str, Any]:
    return {"source": SOURCE, "error": message, **extra}


def _validate_dates(checkin: str | None, checkout: str | None) -> None:
    if bool(checkin) != bool(checkout):
        raise ValueError("Provide both checkin and checkout, or neither.")
    if checkin and checkout:
        nights = (date.fromisoformat(checkout) - date.fromisoformat(checkin)).days
        if nights <= 0:
            raise ValueError("checkout must be after checkin.")
        if nights > MAX_NIGHTS:
            raise ValueError(f"Stays longer than {MAX_NIGHTS} nights are not supported.")


@mcp.tool(annotations=READ_ONLY)
async def airbnb_search(
    location: str,
    checkin: str | None = None,
    checkout: str | None = None,
    adults: int = 2,
    children: int = 0,
    min_price: int | None = None,
    max_price: int | None = None,
    entire_home_only: bool = False,
    min_bedrooms: int | None = None,
    currency: str = "USD",
    max_results: int = 5,
) -> dict[str, Any]:
    """Search Airbnb for villas and homes in a location, with photos, ratings and prices.

    Use this for competitor and market-rate research (e.g. "what do private pool villas in
    Canggu charge for Dec 10-13?"). The chat UI shows the results as photo cards automatically.

    Args:
        location: Area to search, e.g. "Ubud, Bali" or "Canggu, Bali"
        checkin: Check-in date, YYYY-MM-DD, e.g. "2026-12-10" (optional, but needed for stay prices)
        checkout: Check-out date, YYYY-MM-DD, e.g. "2026-12-13"
        adults: Number of adult guests, e.g. 2
        children: Number of children, e.g. 0
        min_price: Minimum nightly price in `currency`, e.g. 100
        max_price: Maximum nightly price in `currency`, e.g. 400
        entire_home_only: Only whole homes/villas, no private rooms. Use true when comparing with villas.
        min_bedrooms: Minimum number of bedrooms, e.g. 2
        currency: ISO currency code for prices, e.g. "USD" or "IDR"
        max_results: Number of listings to return, 1-10 (default 5)

    Returns:
        Dict with query, price_summary (min/median/max per night) and results
        (name, photo, rating out of 5, review_count, badge, price_total, price_per_night, url).
    """
    currency = (currency or "USD").upper()
    max_results = max(1, min(int(max_results), 10))
    try:
        _validate_dates(checkin, checkout)
    except ValueError as e:
        return _error(str(e), results=[])

    params = {
        "checkin": checkin,
        "checkout": checkout,
        "adults": adults,
        "children": children,
        "price_min": min_price,
        "price_max": max_price,
        "room_types[]": "Entire home/apt" if entire_home_only else None,
        "min_bedrooms": min_bedrooms,
        "currency": currency,
    }
    cache_key = cache.key("search", {"location": location.lower().strip(), **params})
    try:
        cached = await cache.get(cache_key)
        if cached is None:
            url, state = await scraper.fetch_state(f"/s/{quote(location, safe='')}/homes", params)
            listings = search_results(state, checkin=checkin, checkout=checkout, adults=adults, currency=currency)
            cached = {"url": url, "listings": listings}
            await cache.set(cache_key, cached, SEARCH_TTL)
        return format_search(
            cached["listings"],
            location=location,
            checkin=checkin,
            checkout=checkout,
            adults=adults,
            currency=currency,
            max_results=max_results,
            search_url=cached["url"],
        )
    except AirbnbError as e:
        return _error(str(e), results=[])
    except Exception as e:
        logger.exception("airbnb_search failed")
        return _error(f"Airbnb search failed: {e}", results=[])


@mcp.tool(annotations=READ_ONLY)
async def airbnb_listing_details(
    listing_id: str,
    checkin: str | None = None,
    checkout: str | None = None,
    adults: int = 2,
    currency: str = "USD",
) -> dict[str, Any]:
    """Get details for one Airbnb listing: description, amenities, house rules, host, rating and photos.

    Use the listing ``id`` from airbnb_search results.

    Args:
        listing_id: Airbnb listing ID from airbnb_search, e.g. "1288193758385508971"
        checkin: Check-in date, YYYY-MM-DD (optional, used for the listing link)
        checkout: Check-out date, YYYY-MM-DD (optional)
        adults: Number of adult guests, e.g. 2
        currency: ISO currency code, e.g. "USD"

    Returns:
        Dict with a single ``listing`` including amenities, highlights, house_rules and photos.
    """
    currency = (currency or "USD").upper()
    listing_id = str(listing_id).strip()
    if not listing_id.isdigit():
        return _error("listing_id must be the numeric Airbnb listing ID from airbnb_search.")
    try:
        _validate_dates(checkin, checkout)
    except ValueError as e:
        return _error(str(e))

    cache_key = cache.key("listing", {"id": listing_id, "checkin": checkin, "checkout": checkout, "currency": currency})
    try:
        cached = await cache.get(cache_key)
        if cached is not None:
            return cached
        _, state = await scraper.fetch_state(
            f"/rooms/{listing_id}",
            {"check_in": checkin, "check_out": checkout, "adults": adults, "currency": currency},
        )
        result = format_listing(
            state, listing_id=listing_id, checkin=checkin, checkout=checkout, adults=adults, currency=currency
        )
        await cache.set(cache_key, result, DETAILS_TTL)
        return result
    except AirbnbError as e:
        return _error(str(e))
    except (KeyError, TypeError):
        logger.exception("Unexpected Airbnb listing page layout")
        return _error("Airbnb listing page has an unexpected layout; the listing may be unavailable.")
    except Exception as e:
        logger.exception("airbnb_listing_details failed")
        return _error(f"Airbnb listing details failed: {e}")


# ---------------------------------------------------------------------------
# ASGI app — MCP Streamable HTTP at /mcp plus a /health check
# ---------------------------------------------------------------------------
transport_security = TransportSecuritySettings(
    enable_dns_rebinding_protection=True,
    allowed_hosts=[f"localhost:{PORT}", f"127.0.0.1:{PORT}", f"airbnb-mcp:{PORT}"],
)
mcp_http_app = mcp.streamable_http_app(stateless_http=True, json_response=True, transport_security=transport_security)


async def health(request: Request) -> JSONResponse:
    return JSONResponse(
        {"status": "healthy", "service": "airbnb-mcp", "ignore_robots_txt": scraper.ignore_robots_txt}
    )


@contextlib.asynccontextmanager
async def lifespan(app: Starlette):
    async with mcp.session_manager.run():
        logger.info("Airbnb MCP server started on :%d (Streamable HTTP)", PORT)
        yield


app = Starlette(routes=[Route("/health", health), Mount("/", app=mcp_http_app)], lifespan=lifespan)


def main() -> None:
    uvicorn.run(app, host="0.0.0.0", port=PORT)


if __name__ == "__main__":
    main()
