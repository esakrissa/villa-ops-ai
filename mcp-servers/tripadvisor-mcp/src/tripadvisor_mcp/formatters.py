"""Turn Terra Location payloads into compact, card-friendly places.

Places share the listing shape used by the Booking.com and Airbnb MCP
servers (minus prices), so the chat UI renders them with the same cards:

    {id, name, url, photo, photos, subtitle, location, rating, rating_scale,
     rating_icon_url, review_count, badge, distance_km, description,
     latitude, longitude}
"""

from typing import Any

SOURCE = "tripadvisor"
PHOTO_CDN = "https://media-cdn.tripadvisor.com/media/"
CATEGORY_LABELS = {"ATTRACTION": "Attraction", "RESTAURANT": "Restaurant", "HOTEL": "Hotel"}

# Approximate centres of Bali areas, so the agent can ask for "restaurants near
# Canggu" without a geocoding call. Anything else needs explicit coordinates.
BALI_AREAS: dict[str, tuple[float, float]] = {
    "ubud": (-8.5069, 115.2625),
    "tegallalang": (-8.4335, 115.2790),
    "canggu": (-8.6478, 115.1385),
    "pererenan": (-8.6385, 115.1240),
    "seminyak": (-8.6913, 115.1682),
    "legian": (-8.7032, 115.1696),
    "kuta": (-8.7224, 115.1726),
    "denpasar": (-8.6705, 115.2126),
    "sanur": (-8.6880, 115.2620),
    "jimbaran": (-8.7908, 115.1606),
    "uluwatu": (-8.8291, 115.0849),
    "nusa dua": (-8.8008, 115.2304),
    "nusa penida": (-8.7275, 115.5444),
    "amed": (-8.3486, 115.6466),
    "lovina": (-8.1600, 115.0273),
    "munduk": (-8.2667, 115.0667),
}


def resolve_area(area: str) -> tuple[float, float] | None:
    key = area.lower().replace(", bali", "").replace("bali", "").strip(" ,")
    return BALI_AREAS.get(key)


def photo_url(key: str | None, size: str = "photo-s") -> str | None:
    """Photo keys look like 'photo-o/30/af/1b/0f/name.jpg'; photo-s is the ~550px rendition."""
    if not key:
        return None
    parts = key.split("/", 1)
    if len(parts) == 2 and parts[0].startswith("photo-"):
        key = f"{size}/{parts[1]}"
    return PHOTO_CDN + key


def _localized(values: list[dict[str, Any]] | None) -> str | None:
    """Pick the primary (or English, or first) entry of Terra's localized-value lists."""
    if not values:
        return None
    for pick in (lambda v: v.get("primary"), lambda v: v.get("language") == "en", lambda v: True):
        for value in values:
            if pick(value) and value.get("value"):
                return str(value["value"]).strip()
    return None


def _photo_from(entry: dict[str, Any] | None) -> str | None:
    info = (entry or {}).get("photo") or {}
    return photo_url(info.get("key")) or info.get("original_size_url")


def _rating(location: dict[str, Any]) -> dict[str, Any]:
    overall = (location.get("traveler_ratings") or {}).get("overall") or location.get("overall_rating") or {}
    return {"rating": overall.get("rating"), "count": overall.get("count") or 0, "icon": overall.get("icon_url")}


def format_place(
    entry: dict[str, Any], *, category: str | None = None, photos: list[str] | None = None
) -> dict[str, Any]:
    """Format one search/nearby entry ({location, photo?, distance_kilometers?}) or a bare Location."""
    location = entry.get("location", entry)
    rating = _rating(location)
    address = next((a.get("formatted") for a in location.get("addresses") or [] if a.get("formatted")), None)
    coordinates = location.get("coordinates") or {}
    distance = entry.get("distance_kilometers")
    photo_list = photos if photos is not None else [p for p in [_photo_from(entry.get("photo"))] if p]

    status = location.get("status")
    status = status.get("value") if isinstance(status, dict) else status
    description = _localized(location.get("descriptions"))

    return {
        "id": str(location.get("id")),
        "name": _localized(location.get("names")) or "Tripadvisor place",
        "url": ((location.get("urls") or {}).get("tripadvisor") or {}).get("main"),
        "photo": photo_list[0] if photo_list else None,
        "photos": photo_list[:6],
        "subtitle": CATEGORY_LABELS.get(category or ""),
        "location": location.get("geo") or address,
        "address": address,
        "rating": rating["rating"],
        "rating_scale": 5,
        "rating_label": None,
        "rating_icon_url": rating["icon"],
        "review_count": rating["count"],
        "badge": "Temporarily closed" if status == "TEMPORARILY_CLOSED" else ("Closed" if status == "CLOSED" else None),
        "distance_km": round(distance, 2) if distance is not None else None,
        "description": description[:280] if description else None,
        "latitude": coordinates.get("latitude"),
        "longitude": coordinates.get("longitude"),
    }


def format_places(body: dict[str, Any], *, query: dict[str, Any], category: str | None) -> dict[str, Any]:
    pagination = body.get("pagination") or {}
    return {
        "source": SOURCE,
        "kind": "places",
        "query": query,
        "total_found": pagination.get("total_elements"),
        "results": [format_place(entry, category=category) for entry in body.get("data") or []],
    }


def format_place_details(location: dict[str, Any], photos_body: dict[str, Any] | None) -> dict[str, Any]:
    photos = [p for p in (_photo_from(photo) for photo in (photos_body or {}).get("data") or []) if p]
    place = format_place(location, photos=photos)
    place["description"] = (_localized(location.get("descriptions")) or "")[:600] or None
    place["phone"] = next((p.get("value") for p in location.get("phone_numbers") or [] if p.get("value")), None)
    place["website"] = (location.get("urls") or {}).get("official")
    place["recommended_visit_hours"] = location.get("recommended_visit_length")
    place["photo_count"] = ((location.get("photos") or {}).get("total_count")) or len(photos)
    return {"source": SOURCE, "kind": "listing_details", "listing": place}
