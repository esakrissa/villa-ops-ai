"""Turn Airbnb's embedded page state into compact, card-friendly results.

Listings use the same shape as the Booking.com MCP server so the chat UI
can render photo cards for either source:

    {id, name, url, photo, photos, subtitle, location, rating, rating_scale,
     rating_label, review_count, badge, price_total, price_per_night,
     original_price_total, currency, latitude, longitude}
"""

import base64
import binascii
import re
import statistics
from typing import Any
from urllib.parse import urlencode

from airbnb_mcp.scraper import BASE_URL

SOURCE = "airbnb"
PHOTO_WIDTH = 720
_RATING = re.compile(r"^\s*([\d.]+)\s*\((\d[\d,]*)\)")
_NIGHTS = re.compile(r"(\d+)\s+night")


def _text(value: Any) -> str | None:
    """Unwrap Airbnb's localized-string objects."""
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, dict):
        for key in ("localizedStringWithTranslationPreference", "localizedString", "localizedContent", "text"):
            if value.get(key):
                return str(value[key]).strip()
        if "content" in value:
            return _text(value["content"])
    return None


def _round(value: float | None) -> float | None:
    return round(value, 2) if value is not None else None


def photo_url(url: str | None) -> str | None:
    """Ask Airbnb's image CDN for a card-sized rendition instead of the original upload."""
    if not url:
        return None
    return f"{url.split('?')[0]}?im_w={PHOTO_WIDTH}"


def parse_price(text: str | None) -> float | None:
    """'$1,234' / 'Rp 1,597,000' / '€99.50' → number (pages are requested in en-US formatting)."""
    if not text:
        return None
    digits = re.sub(r"[^\d.,]", "", text).replace(",", "")
    try:
        return float(digits) if digits else None
    except ValueError:
        return None


def nights_from_qualifier(qualifier: str | None) -> int | None:
    """'for 3 nights' → 3, 'night' → 1."""
    if not qualifier:
        return None
    match = _NIGHTS.search(qualifier)
    if match:
        return int(match.group(1))
    return 1 if "night" in qualifier else None


def parse_rating(localized: str | None) -> tuple[float | None, int, str | None]:
    """'4.97 (37)' → (4.97, 37, None); 'New' → (None, 0, 'New')."""
    match = _RATING.match(localized or "")
    if match:
        return float(match.group(1)), int(match.group(2).replace(",", "")), None
    return None, 0, _text(localized)


def decode_listing_id(encoded: str | None) -> str | None:
    """demandStayListing.id is base64('DemandStayListing:<id>')."""
    if not encoded:
        return None
    try:
        return base64.b64decode(encoded).decode().split(":")[-1]
    except (binascii.Error, UnicodeDecodeError):
        return None


def listing_url(listing_id: str, *, checkin: str | None, checkout: str | None, adults: int, currency: str) -> str:
    query = {"check_in": checkin, "check_out": checkout, "adults": adults, "currency": currency}
    return f"{BASE_URL}/rooms/{listing_id}?{urlencode({k: v for k, v in query.items() if v})}"


def price_summary(results: list[dict[str, Any]]) -> dict[str, Any] | None:
    prices = [r["price_per_night"] for r in results if r.get("price_per_night")]
    if not prices:
        return None
    return {
        "min_per_night": _round(min(prices)),
        "median_per_night": _round(statistics.median(prices)),
        "max_per_night": _round(max(prices)),
    }


def format_search_result(
    result: dict[str, Any], *, checkin: str | None, checkout: str | None, adults: int, currency: str
) -> dict[str, Any] | None:
    stay = result.get("demandStayListing") or {}
    listing_id = decode_listing_id(stay.get("id")) or result.get("propertyId")
    if not listing_id:
        return None

    price_line = (result.get("structuredDisplayPrice") or {}).get("primaryLine") or {}
    total = parse_price(price_line.get("discountedPrice") or price_line.get("price"))
    original = parse_price(price_line.get("originalPrice"))
    nights = nights_from_qualifier(price_line.get("qualifier"))
    rating, review_count, rating_label = parse_rating(result.get("avgRatingLocalized"))
    photos = [photo_url(p.get("picture")) for p in result.get("contextualPictures") or []]
    photos = [p for p in photos if p]
    details = [line.get("body") for line in (result.get("structuredContent") or {}).get("primaryLine") or []]
    coordinate = (stay.get("location") or {}).get("coordinate") or {}

    return {
        "id": str(listing_id),
        "name": _text(result.get("nameLocalized")) or _text(result.get("subtitle")) or "Airbnb listing",
        "url": listing_url(str(listing_id), checkin=checkin, checkout=checkout, adults=adults, currency=currency),
        "photo": photos[0] if photos else None,
        "photos": photos[:3],
        "subtitle": " · ".join(d for d in details if d) or None,
        "location": _text(result.get("title")),
        "rating": rating,
        "rating_scale": 5,
        "rating_label": rating_label,
        "review_count": review_count,
        "badge": next((_text(b.get("text")) for b in result.get("badges") or [] if b.get("text")), None),
        "price_total": _round(total),
        "price_per_night": _round(total / nights) if total and nights else None,
        "original_price_total": _round(original) if original and total and original > total else None,
        "currency": currency,
        "latitude": coordinate.get("latitude"),
        "longitude": coordinate.get("longitude"),
    }


def search_results(state: dict[str, Any], **kwargs: Any) -> list[dict[str, Any]]:
    """All listings on the page (≈18), normalized."""
    results = state["data"]["presentation"]["staysSearch"]["results"]["searchResults"]
    formatted = (format_search_result(r, **kwargs) for r in results if r.get("demandStayListing"))
    return [r for r in formatted if r]


def format_search(
    listings: list[dict[str, Any]],
    *,
    location: str,
    checkin: str | None,
    checkout: str | None,
    adults: int,
    currency: str,
    max_results: int,
    search_url: str,
) -> dict[str, Any]:
    results = listings[:max_results]
    nights = None
    if results and results[0].get("price_total") and results[0].get("price_per_night"):
        nights = round(results[0]["price_total"] / results[0]["price_per_night"])
    return {
        "source": SOURCE,
        "kind": "listings",
        "query": {
            "destination": location,
            "checkin": checkin,
            "checkout": checkout,
            "nights": nights,
            "adults": adults,
            "currency": currency,
        },
        "search_url": search_url,
        "total_found": f"{len(listings)} stays on the first page",
        "price_summary": price_summary(results),
        "results": results,
    }


def _amenities(amenities: dict[str, Any]) -> list[str]:
    """Host-picked preview amenities (pool, kitchen, view…) first, then the full list."""
    groups = [*(amenities.get("previewAmenitiesGroups") or []), *(amenities.get("seeAllAmenitiesGroups") or [])]
    names = [a.get("title") for g in groups for a in g.get("amenities") or [] if a.get("available") and a.get("title")]
    return list(dict.fromkeys(names))


def _photos(pdp: dict[str, Any]) -> list[str]:
    urls = [((e.get("node") or {}).get("image") or {}).get("uri") for e in (pdp.get("heroMedia") or {}).get("edges") or []]
    for stop in (pdp.get("mediaTour") or {}).get("stops") or []:
        urls.extend((item.get("image") or {}).get("uri") for item in stop.get("items") or [])
    return list(dict.fromkeys(p for p in (photo_url(u) for u in urls) if p))


def format_listing(
    state: dict[str, Any], *, listing_id: str, checkin: str | None, checkout: str | None, adults: int, currency: str
) -> dict[str, Any]:
    node = state["data"]["node"]
    pdp = node["pdpPresentation"]
    quality = pdp.get("quality") or {}
    stats = ((quality.get("listingRatingStats") or {}).get("overallRatingStats")) or {}
    location = pdp.get("location") or {}
    host = (pdp.get("hostInfo") or {}).get("passportData") or {}
    description = re.sub(r"<[^>]+>", " ", _text((pdp.get("descriptions") or {}).get("longDescriptionHtml")) or "")
    description = re.sub(r"\s+", " ", description).strip()
    photos = _photos(pdp)
    rules = [
        item.get("title")
        for group in (pdp.get("rules") or {}).get("groupItems") or []
        for item in group.get("items") or []
        if item.get("title")
    ]
    review_count = stats.get("ratingCount")

    return {
        "source": SOURCE,
        "kind": "listing_details",
        "listing": {
            "id": listing_id,
            "name": _text(pdp.get("title")) or "Airbnb listing",
            "url": listing_url(listing_id, checkin=checkin, checkout=checkout, adults=adults, currency=currency),
            "photo": photos[0] if photos else None,
            "photos": photos[:6],
            "subtitle": (pdp.get("sharingConfig") or {}).get("propertyType"),
            "location": location.get("subtitle"),
            "location_summary": location.get("locationSummary"),
            "overview": (pdp.get("overview") or {}).get("items") or [],
            "rating": stats.get("ratingAverage"),
            "rating_scale": 5,
            "rating_label": None,
            "review_count": int(review_count) if review_count else 0,
            "badge": "Guest favorite" if quality.get("isGuestFavorite") else None,
            "host": {"name": host.get("name"), "is_superhost": bool(host.get("isSuperhost"))} if host else None,
            "person_capacity": pdp.get("personCapacity") or node.get("personCapacity"),
            "description": description[:600] or None,
            "highlights": [h for h in (_text(x.get("headline")) for x in pdp.get("highlights") or []) if h][:5],
            "amenities": _amenities(pdp.get("amenities") or {})[:20],
            "house_rules": rules[:8],
            "price_total": None,
            "price_per_night": None,
            "original_price_total": None,
            "currency": currency,
            "latitude": location.get("latitude"),
            "longitude": location.get("longitude"),
        },
    }
