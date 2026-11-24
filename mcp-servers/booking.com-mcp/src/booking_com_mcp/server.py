"""Booking.com MCP server — Streamable HTTP on port 8002.

Tools:
    booking_search_hotels   — destination lookup + hotel search with photos and prices
    booking_hotel_details   — facilities, rooms, photos and the booking.com URL for one hotel

Runs standalone (``python -m booking_com_mcp.server``) or as the ``booking-mcp``
service in VillaOps AI's docker-compose. Responses are cached in Redis to save
RapidAPI quota.
"""

import contextlib
import logging
import os
from datetime import date
from typing import Any

import uvicorn
from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from mcp_types import ToolAnnotations
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

from booking_com_mcp.cache import JsonCache
from booking_com_mcp.client import BookingAPIError, BookingClient
from booking_com_mcp.formatters import (
    SOURCE,
    format_hotel_details,
    format_hotel_search,
    nights_between,
    pick_destination,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("booking-com-mcp")

PORT = int(os.getenv("PORT", "8002"))
DESTINATION_TTL = 30 * 24 * 3600  # destination IDs practically never change
SEARCH_TTL = int(os.getenv("BOOKING_CACHE_TTL", str(6 * 3600)))
MAX_NIGHTS = 30
SORT_OPTIONS = {
    "popularity": "popularity",
    "price": "price",
    "rating": "bayesian_review_score",
    "stars": "class_descending",
}

client = BookingClient(
    api_key=os.getenv("RAPIDAPI_KEY", "").strip(),
    host=os.getenv("RAPIDAPI_BOOKING_HOST", "booking-com15.p.rapidapi.com"),
    cache=JsonCache(os.getenv("REDIS_URL"), prefix="mcp:booking"),
)

mcp = MCPServer(
    name="booking-com-mcp",
    instructions=(
        "Live Booking.com hotel data for market research: search hotels in a destination with "
        "photos, prices and review scores, then fetch details for a specific hotel."
    ),
)

READ_ONLY = ToolAnnotations(read_only_hint=True, open_world_hint=True)


def _error(message: str, **extra: Any) -> dict[str, Any]:
    return {"source": SOURCE, "error": message, **extra}


def _parse_dates(checkin_date: str, checkout_date: str) -> tuple[date, date, int]:
    checkin, checkout = date.fromisoformat(checkin_date), date.fromisoformat(checkout_date)
    nights = nights_between(checkin, checkout)
    if nights <= 0:
        raise ValueError("checkout_date must be after checkin_date.")
    if nights > MAX_NIGHTS:
        raise ValueError(f"Stays longer than {MAX_NIGHTS} nights are not supported.")
    return checkin, checkout, nights


@mcp.tool(annotations=READ_ONLY)
async def booking_search_hotels(
    location: str,
    checkin_date: str,
    checkout_date: str,
    adults: int = 2,
    rooms: int = 1,
    currency: str = "USD",
    sort_by: str = "popularity",
    max_results: int = 5,
) -> dict[str, Any]:
    """Search Booking.com for hotels and villas in a destination, with photos, prices and review scores.

    Use this for competitor and market-rate research (e.g. "what do hotels in Ubud charge
    for Dec 10-13?"). The chat UI shows the results as photo cards automatically.

    Args:
        location: Destination name, e.g. "Ubud", "Canggu", "Seminyak, Bali"
        checkin_date: Check-in date, YYYY-MM-DD, e.g. "2026-12-10"
        checkout_date: Check-out date, YYYY-MM-DD, e.g. "2026-12-13"
        adults: Number of adult guests, e.g. 2
        rooms: Number of rooms, e.g. 1
        currency: ISO currency code for prices, e.g. "USD" or "IDR"
        sort_by: One of "popularity", "price", "rating", "stars"
        max_results: Number of hotels to return, 1-10 (default 5)

    Returns:
        Dict with query, price_summary (min/median/max per night) and results
        (name, photo, rating out of 10, review_count, price_total, price_per_night, url).
    """
    currency = (currency or "USD").upper()
    max_results = max(1, min(int(max_results), 10))
    try:
        _, _, nights = _parse_dates(checkin_date, checkout_date)
    except ValueError as e:
        return _error(str(e), results=[])
    if sort_by not in SORT_OPTIONS:
        return _error(f"sort_by must be one of {', '.join(SORT_OPTIONS)}.", results=[])

    try:
        destinations = await client.get("/api/v1/hotels/searchDestination", {"query": location}, DESTINATION_TTL)
        dest = pick_destination(destinations)
        if dest is None:
            return _error(f"No Booking.com destination found for '{location}'.", results=[])

        data = await client.get(
            "/api/v1/hotels/searchHotels",
            {
                "dest_id": dest["dest_id"],
                "search_type": str(dest["search_type"]).upper(),
                "arrival_date": checkin_date,
                "departure_date": checkout_date,
                "adults": adults,
                "room_qty": rooms,
                "page_number": 1,
                "sort_by": SORT_OPTIONS[sort_by],
                "units": "metric",
                "temperature_unit": "c",
                "languagecode": "en-us",
                "currency_code": currency,
            },
            SEARCH_TTL,
        )
        return format_hotel_search(
            data,
            dest=dest,
            checkin=checkin_date,
            checkout=checkout_date,
            nights=nights,
            adults=adults,
            currency=currency,
            max_results=max_results,
        )
    except BookingAPIError as e:
        return _error(str(e), results=[])
    except Exception as e:
        logger.exception("booking_search_hotels failed")
        return _error(f"Hotel search failed: {e}", results=[])


@mcp.tool(annotations=READ_ONLY)
async def booking_hotel_details(
    hotel_id: str,
    checkin_date: str,
    checkout_date: str,
    adults: int = 2,
    currency: str = "USD",
) -> dict[str, Any]:
    """Get details for one Booking.com hotel: photos, facilities, room types, price and its booking.com URL.

    Use the hotel ``id`` from booking_search_hotels results.

    Args:
        hotel_id: Booking.com hotel ID from booking_search_hotels, e.g. "6048884"
        checkin_date: Check-in date, YYYY-MM-DD, e.g. "2026-12-10"
        checkout_date: Check-out date, YYYY-MM-DD, e.g. "2026-12-13"
        adults: Number of adult guests, e.g. 2
        currency: ISO currency code for prices, e.g. "USD" or "IDR"

    Returns:
        Dict with a single ``listing`` including facilities, highlights, rooms and photos.
    """
    try:
        _, _, nights = _parse_dates(checkin_date, checkout_date)
    except ValueError as e:
        return _error(str(e))
    try:
        data = await client.get(
            "/api/v1/hotels/getHotelDetails",
            {
                "hotel_id": hotel_id,
                "arrival_date": checkin_date,
                "departure_date": checkout_date,
                "adults": adults,
                "room_qty": 1,
                "units": "metric",
                "temperature_unit": "c",
                "languagecode": "en-us",
                "currency_code": (currency or "USD").upper(),
            },
            SEARCH_TTL,
        )
        if not data:
            return _error(f"No details found for hotel {hotel_id}.")
        return format_hotel_details(data, checkin=checkin_date, checkout=checkout_date, nights=nights)
    except BookingAPIError as e:
        return _error(str(e))
    except Exception as e:
        logger.exception("booking_hotel_details failed")
        return _error(f"Hotel details failed: {e}")


# ---------------------------------------------------------------------------
# ASGI app — MCP Streamable HTTP at /mcp plus a /health check
# ---------------------------------------------------------------------------
transport_security = TransportSecuritySettings(
    enable_dns_rebinding_protection=True,
    allowed_hosts=[f"localhost:{PORT}", f"127.0.0.1:{PORT}", f"booking-mcp:{PORT}"],
)
mcp_http_app = mcp.streamable_http_app(stateless_http=True, json_response=True, transport_security=transport_security)


async def health(request: Request) -> JSONResponse:
    return JSONResponse({"status": "healthy", "service": "booking-com-mcp", "api_key_set": client.configured})


@contextlib.asynccontextmanager
async def lifespan(app: Starlette):
    async with mcp.session_manager.run():
        logger.info("Booking.com MCP server started on :%d (Streamable HTTP)", PORT)
        yield


app = Starlette(routes=[Route("/health", health), Mount("/", app=mcp_http_app)], lifespan=lifespan)


def main() -> None:
    uvicorn.run(app, host="0.0.0.0", port=PORT)


if __name__ == "__main__":
    main()
