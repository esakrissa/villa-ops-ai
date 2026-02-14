"""Guest MCP tools — lookup, create, and update guests."""

import logging
import uuid as uuid_mod

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.mcp import get_session_factory, mcp
from app.models.booking import Booking
from app.models.guest import Guest
from app.models.property import Property

logger = logging.getLogger(__name__)


def _serialize_guest(g: Guest, include_bookings: bool = False, owner_uuid: uuid_mod.UUID | None = None) -> dict:
    """Serialize a Guest ORM object to a plain dict."""
    data = {
        "id": str(g.id),
        "name": g.name,
        "email": g.email,
        "phone": g.phone,
        "nationality": g.nationality,
        "notes": g.notes,
    }
    if include_bookings and g.bookings:
        bookings = g.bookings
        if owner_uuid:
            bookings = [
                b for b in bookings
                if b.property and b.property.owner_id == owner_uuid
            ]
        data["bookings"] = [
            {
                "id": str(b.id),
                "property_name": b.property.name if b.property else None,
                "check_in": b.check_in.isoformat(),
                "check_out": b.check_out.isoformat(),
                "status": b.status,
                "total_price": str(b.total_price) if b.total_price else None,
            }
            for b in bookings
        ]
    elif include_bookings:
        data["bookings"] = []
    return data


@mcp.tool()
async def guest_lookup(
    name: str | None = None,
    email: str | None = None,
    include_bookings: bool = True,
    limit: int = 10,
    user_id: str | None = None,
) -> dict:
    """Look up guests by name or email, optionally including their booking history.

    Searches guests who have bookings at the user's properties first,
    then falls back to a global search if no results are found (so newly
    created guests without bookings can still be found).

    Args:
        name: Fuzzy match on guest name (e.g. "sarah")
        email: Fuzzy match on guest email
        include_bookings: Whether to include each guest's booking history (default True)
        limit: Maximum number of guests returned (default 10)
        user_id: UUID of the current user (filters bookings to their properties)

    Returns:
        Dict with guests list (each with optional bookings), total count, and query filters.
    """
    try:
        session_factory = get_session_factory()
        async with session_factory() as session:
            owner_uuid = uuid_mod.UUID(user_id) if user_id else None

            # First: search guests with bookings at the user's properties
            guests = await _search_guests(
                session, name, email, include_bookings, limit,
                owner_filter=owner_uuid,
            )

            # Fallback: if no results and we had an owner filter, search globally
            # so newly created guests (no bookings yet) can be found
            if not guests and owner_uuid:
                guests = await _search_guests(
                    session, name, email, include_bookings, limit,
                    owner_filter=None,
                )

            return {
                "guests": [_serialize_guest(g, include_bookings, owner_uuid) for g in guests],
                "total": len(guests),
                "query_filters": {
                    k: v for k, v in {"name": name, "email": email}.items() if v is not None
                },
            }
    except Exception as e:
        logger.exception("guest_lookup failed")
        return {"error": str(e), "guests": [], "total": 0}


async def _search_guests(
    session,
    name: str | None,
    email: str | None,
    include_bookings: bool,
    limit: int,
    owner_filter: uuid_mod.UUID | None,
) -> list[Guest]:
    """Search guests, optionally filtered to those with bookings at owner's properties."""
    query = select(Guest)

    if owner_filter:
        query = (
            query
            .join(Booking, Guest.id == Booking.guest_id)
            .join(Property, Booking.property_id == Property.id)
            .where(Property.owner_id == owner_filter)
            .distinct()
        )

    if include_bookings:
        query = query.options(
            selectinload(Guest.bookings).selectinload(Booking.property)
        )

    if name:
        query = query.where(Guest.name.ilike(f"%{name}%"))
    if email:
        query = query.where(Guest.email.ilike(f"%{email}%"))

    query = query.order_by(Guest.created_at.desc()).limit(limit)
    result = await session.execute(query)
    return list(result.scalars().all())


@mcp.tool()
async def guest_create(
    name: str,
    email: str,
    phone: str | None = None,
    nationality: str | None = None,
    notes: str | None = None,
    user_id: str | None = None,
) -> dict:
    """Create a new guest record.

    Use this when a guest doesn't exist in the system and needs to be created
    before a booking can be made. Call guest_lookup first to check if the guest
    already exists.

    Args:
        name: Full name of the guest
        email: Email address (must be unique across all guests)
        phone: Phone number (optional)
        nationality: Nationality (optional)
        notes: Additional notes about the guest (optional)
        user_id: UUID of the current user (for logging only)

    Returns:
        Dict with created guest details (including UUID) or error.
    """
    if not name or not name.strip():
        return {"error": "Guest name is required.", "guest": None}
    if not email or not email.strip():
        return {"error": "Guest email is required.", "guest": None}

    try:
        session_factory = get_session_factory()
        async with session_factory() as session:
            # Check for existing guest with same email
            result = await session.execute(
                select(Guest).where(Guest.email.ilike(email.strip()))
            )
            existing = result.scalar_one_or_none()
            if existing:
                return {
                    "guest": _serialize_guest(existing),
                    "already_existed": True,
                    "message": f"Guest with email '{email}' already exists.",
                }

            guest = Guest(
                name=name.strip(),
                email=email.strip(),
                phone=phone,
                nationality=nationality,
                notes=notes,
            )
            session.add(guest)
            await session.flush()
            await session.refresh(guest)
            await session.commit()

            logger.info(
                "Guest created: %s <%s> (by user %s)",
                guest.name, guest.email, user_id or "unknown",
            )

            return {
                "guest": _serialize_guest(guest),
                "already_existed": False,
            }
    except Exception as e:
        logger.exception("guest_create failed")
        return {"error": str(e), "guest": None}


@mcp.tool()
async def guest_update(
    guest_id: str,
    name: str | None = None,
    email: str | None = None,
    phone: str | None = None,
    nationality: str | None = None,
    notes: str | None = None,
    user_id: str | None = None,
) -> dict:
    """Update an existing guest's details.

    Args:
        guest_id: UUID of the guest to update (get from guest_lookup or guest_create)
        name: Updated full name (optional)
        email: Updated email address (optional, must be unique)
        phone: Updated phone number (optional)
        nationality: Updated nationality (optional)
        notes: Updated notes (optional)
        user_id: UUID of the current user (for logging only)

    Returns:
        Dict with updated guest details or error.
    """
    try:
        gid = uuid_mod.UUID(guest_id)
    except ValueError:
        return {"error": f"Invalid guest_id: '{guest_id}'", "guest": None}

    if not any([name, email, phone, nationality, notes]):
        return {"error": "At least one field to update must be provided.", "guest": None}

    try:
        session_factory = get_session_factory()
        async with session_factory() as session:
            guest = await session.get(Guest, gid)
            if guest is None:
                return {"error": f"Guest '{guest_id}' not found.", "guest": None}

            # Check email uniqueness if changing email
            if email and email.strip().lower() != guest.email.lower():
                result = await session.execute(
                    select(Guest).where(Guest.email.ilike(email.strip()))
                )
                existing = result.scalar_one_or_none()
                if existing:
                    return {
                        "error": f"Email '{email}' is already used by another guest.",
                        "guest": None,
                    }

            if name is not None:
                guest.name = name.strip()
            if email is not None:
                guest.email = email.strip()
            if phone is not None:
                guest.phone = phone
            if nationality is not None:
                guest.nationality = nationality
            if notes is not None:
                guest.notes = notes

            session.add(guest)
            await session.flush()
            await session.refresh(guest)
            await session.commit()

            logger.info(
                "Guest updated: %s <%s> (by user %s)",
                guest.name, guest.email, user_id or "unknown",
            )

            return {"guest": _serialize_guest(guest)}
    except Exception as e:
        logger.exception("guest_update failed")
        return {"error": str(e), "guest": None}
