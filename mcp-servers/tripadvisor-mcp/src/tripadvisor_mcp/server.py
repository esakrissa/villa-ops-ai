"""Tripadvisor MCP server — Streamable HTTP on port 8004.

Tools:
    tripadvisor_search_nearby_locations — top attractions / restaurants / hotels around a Bali area or point
    tripadvisor_search_locations        — find a specific place by name
    tripadvisor_get_location_details    — description, contact, rating and photos for one place

Uses the Tripadvisor Terra Partner API (the legacy Content API is retired).
Terra bills per location returned and forbids caching content, so every tool
asks only for the handful of results the chat UI shows.
"""

import asyncio
import contextlib
import logging
import os
from typing import Any

import uvicorn
from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from mcp_types import ToolAnnotations
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

from tripadvisor_mcp.client import TripadvisorAPIError, TripadvisorClient
from tripadvisor_mcp.formatters import BALI_AREAS, SOURCE, format_place_details, format_places, resolve_area

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tripadvisor-mcp")

PORT = int(os.getenv("PORT", "8004"))
CATEGORIES = ("ATTRACTION", "RESTAURANT", "HOTEL")
MAX_RADIUS_KM = 8

client = TripadvisorClient(api_key=os.getenv("TRIPADVISOR_API_KEY", "").strip())

mcp = MCPServer(
    name="tripadvisor-mcp",
    instructions=(
        "Tripadvisor places for Bali: top-rated attractions, restaurants and hotels around an area, "
        "with ratings, review counts and photos, for guest recommendations and local market research."
    ),
)

READ_ONLY = ToolAnnotations(read_only_hint=True, open_world_hint=True)


def _error(message: str, **extra: Any) -> dict[str, Any]:
    return {"source": SOURCE, "error": message, **extra}


def _category(category: str | None) -> str | None:
    if not category:
        return None
    value = category.strip().upper().rstrip("S")  # accept "restaurants", "Attractions"
    if value not in CATEGORIES:
        raise ValueError(f"category must be one of {', '.join(c.lower() for c in CATEGORIES)}.")
    return value


@mcp.tool(annotations=READ_ONLY)
async def tripadvisor_search_nearby_locations(
    area: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    category: str = "attraction",
    radius_km: float = 3,
    min_rating: float | None = None,
    sort_by: str = "rating",
    max_results: int = 5,
) -> dict[str, Any]:
    """Find top Tripadvisor attractions, restaurants or hotels near a Bali area or coordinates, with photos.

    Use this for guest recommendations ("what should my guests do near Ubud?") and to see what's
    around a property. The chat UI shows the results as photo cards automatically.

    Args:
        area: Bali area name, e.g. "Ubud", "Canggu", "Seminyak", "Uluwatu", "Sanur", "Nusa Dua"
        latitude: Centre latitude instead of an area, e.g. -8.5069
        longitude: Centre longitude instead of an area, e.g. 115.2625
        category: "attraction", "restaurant" or "hotel"
        radius_km: Search radius in km, 0.5-8 (default 3)
        min_rating: Minimum Tripadvisor rating 1-5, e.g. 4.5
        sort_by: "rating" (default) or "distance"
        max_results: Number of places, 1-10 (default 5)

    Returns:
        Dict with results (name, photo, rating out of 5, review_count, distance_km, url).
    """
    try:
        category_code = _category(category)
    except ValueError as e:
        return _error(str(e), results=[])
    if area and (latitude is None or longitude is None):
        centre = resolve_area(area)
        if centre is None:
            return _error(
                f"Unknown area '{area}'. Use one of: {', '.join(sorted(BALI_AREAS))}, or pass latitude/longitude.",
                results=[],
            )
        latitude, longitude = centre
    if latitude is None or longitude is None:
        return _error("Provide an area or both latitude and longitude.", results=[])
    if sort_by not in ("rating", "distance"):
        return _error('sort_by must be "rating" or "distance".', results=[])
    radius_km = max(0.5, min(float(radius_km), MAX_RADIUS_KM))
    if sort_by == "rating" and min_rating is None:
        min_rating = 3.0  # Terra sorts unrated places first under rating,desc; this drops them
    max_results = max(1, min(int(max_results), 10))

    try:
        body = await client.get(
            "/locations/nearby",
            {
                "lat": latitude,
                "lon": longitude,
                "radius": radius_km,
                "unit": "KM",
                "category": category_code,
                "min_rating": min_rating,
                "sort": "rating,desc" if sort_by == "rating" else "distance,asc",
                "include_photo": "true",
                "size": max_results,
            },
        )
        return format_places(
            body,
            query={
                "area": area,
                "latitude": latitude,
                "longitude": longitude,
                "radius_km": radius_km,
                "category": category_code,
            },
            category=category_code,
        )
    except TripadvisorAPIError as e:
        return _error(str(e), results=[])
    except Exception as e:
        logger.exception("tripadvisor_search_nearby_locations failed")
        return _error(f"Tripadvisor nearby search failed: {e}", results=[])


@mcp.tool(annotations=READ_ONLY)
async def tripadvisor_search_locations(
    query: str,
    geo_name: str = "Bali",
    category: str | None = None,
    max_results: int = 5,
) -> dict[str, Any]:
    """Find a specific place on Tripadvisor by name, e.g. a restaurant, beach club, temple or hotel.

    Use this to look up a named place and get its Tripadvisor ID, rating and link.
    For "best places near X", use tripadvisor_search_nearby_locations instead.

    Args:
        query: Place name, e.g. "Locavore", "Tanah Lot Temple", "Potato Head"
        geo_name: City or region to search in, e.g. "Ubud" or "Bali"
        category: Optional "attraction", "restaurant" or "hotel"
        max_results: Number of places, 1-10 (default 5)

    Returns:
        Dict with results (id, name, rating out of 5, review_count, address, url).
    """
    try:
        category_code = _category(category)
    except ValueError as e:
        return _error(str(e), results=[])
    max_results = max(1, min(int(max_results), 10))
    try:
        body = await client.get(
            "/locations/search",
            {
                "query": query,
                "geo_name": geo_name,
                "country_code": "ID" if "bali" in geo_name.lower() else None,
                "category": category_code,
                "search_type": "COMBINED",
                "size": max_results,
            },
        )
        return format_places(
            body, query={"query": query, "geo_name": geo_name, "category": category_code}, category=category_code
        )
    except TripadvisorAPIError as e:
        return _error(str(e), results=[])
    except Exception as e:
        logger.exception("tripadvisor_search_locations failed")
        return _error(f"Tripadvisor search failed: {e}", results=[])


@mcp.tool(annotations=READ_ONLY)
async def tripadvisor_get_location_details(location_id: str, max_photos: int = 5) -> dict[str, Any]:
    """Get details for one Tripadvisor place: description, rating, address, phone, website and photos.

    Use the ``id`` from tripadvisor_search_nearby_locations or tripadvisor_search_locations.

    Args:
        location_id: Tripadvisor location ID, e.g. "13964849"
        max_photos: Number of photos to include, 0-10 (default 5)

    Returns:
        Dict with a single ``listing`` (name, rating, review_count, description, phone, website, photos, url).
    """
    location_id = str(location_id).strip()
    if not location_id.isdigit():
        return _error("location_id must be the numeric Tripadvisor ID from a search result.")
    max_photos = max(0, min(int(max_photos), 10))
    try:
        details_call = client.get(f"/locations/{location_id}")
        if max_photos:
            location, photos = await asyncio.gather(
                details_call, client.get(f"/locations/{location_id}/photos", {"size": max_photos})
            )
        else:
            location, photos = await details_call, None
        if isinstance(location, dict) and "id" not in location and isinstance(location.get("data"), dict):
            location = location["data"]
        return format_place_details(location, photos)
    except TripadvisorAPIError as e:
        if e.status == 404:
            return _error(f"Tripadvisor location {location_id} was not found or is not on this API key's allowlist.")
        return _error(str(e))
    except Exception as e:
        logger.exception("tripadvisor_get_location_details failed")
        return _error(f"Tripadvisor details failed: {e}")


# ---------------------------------------------------------------------------
# ASGI app — MCP Streamable HTTP at /mcp plus a /health check
# ---------------------------------------------------------------------------
transport_security = TransportSecuritySettings(
    enable_dns_rebinding_protection=True,
    allowed_hosts=[f"localhost:{PORT}", f"127.0.0.1:{PORT}", f"tripadvisor-mcp:{PORT}"],
)
mcp_http_app = mcp.streamable_http_app(stateless_http=True, json_response=True, transport_security=transport_security)


async def health(request: Request) -> JSONResponse:
    return JSONResponse({"status": "healthy", "service": "tripadvisor-mcp", "api_key_set": client.configured})


@contextlib.asynccontextmanager
async def lifespan(app: Starlette):
    async with mcp.session_manager.run():
        logger.info("Tripadvisor MCP server started on :%d (Streamable HTTP)", PORT)
        yield


app = Starlette(routes=[Route("/health", health), Mount("/", app=mcp_http_app)], lifespan=lifespan)


def main() -> None:
    uvicorn.run(app, host="0.0.0.0", port=PORT)


if __name__ == "__main__":
    main()
