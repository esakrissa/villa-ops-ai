"""Turn raw booking-com15 payloads into compact, card-friendly results.

Every search tool returns the same listing shape (shared with the Airbnb
MCP server) so the chat UI can render photo cards for either source:

    {id, name, url, photo, photos, subtitle, location, rating, rating_scale,
     rating_label, review_count, badge, price_total, price_per_night,
     original_price_total, currency, latitude, longitude}
"""

import re
import statistics
from datetime import date
from typing import Any
from urllib.parse import urlencode

SOURCE = "booking.com"
# Booking.com search results carry square500/square1024 photos; max750 keeps the original aspect ratio.
_PHOTO_SIZE = re.compile(r"/images/hotel/[a-z0-9x]+/")
_PERKS = ("Free cancellation", "Breakfast included", "No prepayment needed")


def nights_between(checkin: date, checkout: date) -> int:
    return (checkout - checkin).days


def resize_photo(url: str | None, size: str = "max750") -> str | None:
    return _PHOTO_SIZE.sub(f"/images/hotel/{size}/", url) if url else None


def strip_html(text: str | None) -> str:
    return re.sub(r"<[^>]+>", "", text or "").replace("\xa0", " ").strip()


def _round(value: float | None) -> float | None:
    return round(value, 2) if value is not None else None


def price_summary(results: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Min / median / max nightly price across results, for quick rate comparison."""
    prices = [r["price_per_night"] for r in results if r.get("price_per_night")]
    if not prices:
        return None
    return {
        "min_per_night": _round(min(prices)),
        "median_per_night": _round(statistics.median(prices)),
        "max_per_night": _round(max(prices)),
    }


def pick_destination(destinations: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Pick the best destination match; the API ranks them, so the first usable one wins."""
    for dest in destinations or []:
        if dest.get("dest_id") and dest.get("search_type"):
            return dest
    return None


def search_url(hotel_id: int | str, name: str, dest: dict[str, Any], checkin: str, checkout: str, adults: int) -> str:
    """Booking.com search page with this hotel pinned on top (search results carry no hotel URL)."""
    query = {
        "ss": name,
        "dest_id": dest.get("dest_id"),
        "dest_type": dest.get("search_type"),
        "checkin": checkin,
        "checkout": checkout,
        "group_adults": adults,
        "no_rooms": 1,
        "highlighted_hotels": hotel_id,
    }
    return f"https://www.booking.com/searchresults.html?{urlencode(query)}"


def format_hotel(entry: dict[str, Any], *, nights: int, dest: dict[str, Any], checkin: str, checkout: str, adults: int) -> dict[str, Any]:
    prop = entry.get("property", {})
    breakdown = prop.get("priceBreakdown") or {}
    gross = breakdown.get("grossPrice") or {}
    strike = breakdown.get("strikethroughPrice") or {}
    total = gross.get("value")
    original = strike.get("value")
    label = entry.get("accessibilityLabel") or ""
    photos = [resize_photo(u) for u in (prop.get("photoUrls") or [])]
    photos = list(dict.fromkeys(p for p in photos if p))  # square500 + square1024 collapse to one

    hotel_id = prop.get("id") or entry.get("hotel_id")
    name = prop.get("name", "Unknown")
    return {
        "id": str(hotel_id),
        "name": name,
        "url": search_url(hotel_id, name, dest, checkin, checkout, adults),
        "photo": photos[0] if photos else None,
        "photos": photos[:3],
        "subtitle": strip_html(prop.get("recommendedUnitsConfigurationLabel")) or None,
        "location": prop.get("wishlistName"),
        "stars": prop.get("propertyClass") or prop.get("accuratePropertyClass") or None,
        "rating": prop.get("reviewScore") or None,
        "rating_scale": 10,
        "rating_label": prop.get("reviewScoreWord") or None,
        "review_count": prop.get("reviewCount") or 0,
        "badge": next((perk for perk in _PERKS if perk.lower() in label.lower()), None),
        "price_total": _round(total),
        "price_per_night": _round(total / nights) if total and nights else None,
        "original_price_total": _round(original) if original and total and original > total else None,
        "currency": gross.get("currency"),
        "latitude": prop.get("latitude"),
        "longitude": prop.get("longitude"),
    }


def format_hotel_search(
    data: dict[str, Any],
    *,
    dest: dict[str, Any],
    checkin: str,
    checkout: str,
    nights: int,
    adults: int,
    currency: str,
    max_results: int,
) -> dict[str, Any]:
    hotels = [h for h in (data or {}).get("hotels", []) if "property" in h]
    results = [
        format_hotel(h, nights=nights, dest=dest, checkin=checkin, checkout=checkout, adults=adults) for h in hotels
    ][:max_results]
    meta = (data or {}).get("meta") or [{}]
    return {
        "source": SOURCE,
        "kind": "listings",
        "query": {
            "destination": dest.get("label") or dest.get("name"),
            "checkin": checkin,
            "checkout": checkout,
            "nights": nights,
            "adults": adults,
            "currency": currency,
        },
        "total_found": meta[0].get("title") if meta else None,
        "price_summary": price_summary(results),
        "results": results,
    }


def _amount(block: dict[str, Any] | None) -> float | None:
    return (block or {}).get("value")


def format_hotel_details(data: dict[str, Any], *, checkin: str, checkout: str, nights: int) -> dict[str, Any]:
    price = data.get("composite_price_breakdown") or {}
    raw = data.get("rawData") or {}

    photos: list[str] = []
    for room in (data.get("rooms") or {}).values():
        for photo in room.get("photos") or []:
            url = photo.get("url_max750") or photo.get("url_original")
            if url and url not in photos:
                photos.append(url)
    main_photo = resize_photo(next(iter(raw.get("photoUrls") or []), None))
    if main_photo:
        photos.insert(0, main_photo)

    facilities = [f.get("name") for f in (data.get("facilities_block") or {}).get("facilities", []) if f.get("name")]
    highlights = [h.get("name") for h in data.get("property_highlight_strip") or [] if h.get("name")]
    rooms = []
    for block in data.get("block") or []:
        name = block.get("name") or block.get("room_name")
        if name and name not in [r["name"] for r in rooms]:
            rooms.append({"name": name, "breakfast_included": bool(block.get("breakfast_included"))})

    total = _amount(price.get("gross_amount"))
    hotel_id = data.get("hotel_id")
    return {
        "source": SOURCE,
        "kind": "listing_details",
        "listing": {
            "id": str(hotel_id),
            "name": data.get("hotel_name"),
            "url": data.get("url"),
            "photo": photos[0] if photos else None,
            "photos": photos[:6],
            "subtitle": data.get("accommodation_type_name"),
            "location": ", ".join(p for p in (data.get("district"), data.get("city")) if p) or None,
            "address": data.get("address"),
            "distance_to_center_km": _round(data.get("distance_to_cc")),
            "stars": raw.get("propertyClass") or None,
            "rating": raw.get("reviewScore") or None,
            "rating_scale": 10,
            "rating_label": raw.get("reviewScoreWord") or None,
            "review_count": data.get("review_nr") or 0,
            "badge": "Breakfast included" if data.get("hotel_include_breakfast") else None,
            "price_total": _round(total),
            "price_per_night": _round(_amount(price.get("gross_amount_per_night")))
            or (_round(total / nights) if total and nights else None),
            "original_price_total": _round(_amount(price.get("strikethrough_amount"))),
            "currency": (price.get("gross_amount") or {}).get("currency") or data.get("currency_code"),
            "latitude": data.get("latitude"),
            "longitude": data.get("longitude"),
            "available_rooms": data.get("available_rooms"),
            "checkin": checkin,
            "checkout": checkout,
            "highlights": highlights[:8],
            "facilities": facilities[:12],
            "rooms": rooms[:4],
            "important_info": [
                strip_html(i.get("phrase")) for i in (data.get("hotel_important_information_with_codes") or [])[:3]
            ],
        },
    }
