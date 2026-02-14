"""Booking MCP tools — search, create, and update bookings."""

import logging
import uuid
from datetime import date
from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.mcp import get_session_factory, mcp
from app.models.booking import Booking
from app.models.guest import Guest
from app.models.property import Property

VALID_BOOKING_STATUSES = {"pending", "confirmed", "checked_in", "checked_out", "cancelled"}

logger = logging.getLogger(__name__)


@mcp.tool()
async def booking_search(
    property_name: str | None = None,
    property_id: str | None = None,
    guest_name: str | None = None,
    status: str | None = None,
    check_in_from: str | None = None,
    check_in_to: str | None = None,
    limit: int = 20,
    user_id: str | None = None,
) -> dict:
    """Search bookings by property, guest, status, or date range.

    Args:
        property_name: Fuzzy match on property name (e.g. "canggu")
        property_id: Exact UUID of a property
        guest_name: Fuzzy match on guest name (e.g. "sarah")
        status: Filter by booking status (pending, confirmed, checked_in, checked_out, cancelled)
        check_in_from: Bookings with check_in >= this date (YYYY-MM-DD)
        check_in_to: Bookings with check_in <= this date (YYYY-MM-DD)
        limit: Maximum number of results (default 20)
        user_id: UUID of the current user (filters to only their properties)

    Returns:
        Dict with bookings list, total count, and applied query filters.
    """
    try:
        session_factory = get_session_factory()
        async with session_factory() as session:
            query = (
                select(Booking)
                .join(Property, Booking.property_id == Property.id)
                .join(Guest, Booking.guest_id == Guest.id)
                .options(selectinload(Booking.property), selectinload(Booking.guest))
            )

            # Filter by owner
            if user_id:
                query = query.where(Property.owner_id == uuid.UUID(user_id))

            # Apply dynamic filters
            if property_name:
                query = query.where(Property.name.ilike(f"%{property_name}%"))
            if property_id:
                query = query.where(Booking.property_id == uuid.UUID(property_id))
            if guest_name:
                query = query.where(Guest.name.ilike(f"%{guest_name}%"))
            if status:
                query = query.where(Booking.status == status)
            if check_in_from:
                query = query.where(Booking.check_in >= date.fromisoformat(check_in_from))
            if check_in_to:
                query = query.where(Booking.check_in <= date.fromisoformat(check_in_to))

            query = query.order_by(Booking.check_in.desc()).limit(limit)
            result = await session.execute(query)
            bookings = list(result.scalars().all())

            return {
                "bookings": [
                    {
                        "id": str(b.id),
                        "property_name": b.property.name if b.property else None,
                        "property_id": str(b.property_id),
                        "guest_name": b.guest.name if b.guest else None,
                        "guest_email": b.guest.email if b.guest else None,
                        "check_in": b.check_in.isoformat(),
                        "check_out": b.check_out.isoformat(),
                        "num_guests": b.num_guests,
                        "status": b.status,
                        "total_price": str(b.total_price) if b.total_price else None,
                        "special_requests": b.special_requests,
                    }
                    for b in bookings
                ],
                "total": len(bookings),
                "query_filters": {
                    k: v
                    for k, v in {
                        "property_name": property_name,
                        "property_id": property_id,
                        "guest_name": guest_name,
                        "status": status,
                        "check_in_from": check_in_from,
                        "check_in_to": check_in_to,
                    }.items()
                    if v is not None
                },
            }
    except Exception as e:
        logger.exception("booking_search failed")
        return {"error": str(e), "bookings": [], "total": 0}


def _serialize_booking(b: Booking) -> dict:
    """Serialize a Booking ORM object to a plain dict."""
    return {
        "id": str(b.id),
        "property_name": b.property.name if b.property else None,
        "property_id": str(b.property_id),
        "guest_name": b.guest.name if b.guest else None,
        "guest_email": b.guest.email if b.guest else None,
        "check_in": b.check_in.isoformat(),
        "check_out": b.check_out.isoformat(),
        "num_guests": b.num_guests,
        "status": b.status,
        "total_price": str(b.total_price) if b.total_price else None,
        "special_requests": b.special_requests,
    }


async def _check_date_conflict(
    session, property_id: uuid.UUID, check_in: date, check_out: date,
    exclude_booking_id: uuid.UUID | None = None,
) -> list[Booking]:
    """Return overlapping non-cancelled bookings for the given property and dates."""
    query = select(Booking).where(
        Booking.property_id == property_id,
        Booking.status != "cancelled",
        Booking.check_in < check_out,
        Booking.check_out > check_in,
    ).options(selectinload(Booking.guest))
    if exclude_booking_id is not None:
        query = query.where(Booking.id != exclude_booking_id)
    result = await session.execute(query)
    return list(result.scalars().all())


@mcp.tool()
async def booking_create(
    property_id: str,
    guest_id: str,
    check_in: str,
    check_out: str,
    num_guests: int = 1,
    status: str = "pending",
    total_price: str | None = None,
    special_requests: str | None = None,
    user_id: str | None = None,
) -> dict:
    """Create a new booking with availability validation.

    IMPORTANT: property_id and guest_id must be UUIDs, not names.
    - To get property_id: call property_list() or property_manage(action="check_availability")
    - To get guest_id: call guest_lookup(name="...") or guest_create(name="...", email="...")

    Args:
        property_id: UUID of the property (get from property_list or property_manage)
        guest_id: UUID of the guest (get from guest_lookup or guest_create)
        check_in: Check-in date (YYYY-MM-DD)
        check_out: Check-out date (YYYY-MM-DD)
        num_guests: Number of guests (default 1)
        status: Initial status — "pending" or "confirmed" (default "pending")
        total_price: Total price for the stay (optional)
        special_requests: Special requests from the guest (optional)
        user_id: UUID of the current user (verifies property ownership)

    Returns:
        Dict with created booking details, or error if validation fails.
    """
    try:
        ci = date.fromisoformat(check_in)
        co = date.fromisoformat(check_out)
    except ValueError as e:
        return {"error": f"Invalid date format: {e}", "booking": None}

    if co <= ci:
        return {"error": "check_out must be after check_in.", "booking": None}

    if status not in VALID_BOOKING_STATUSES:
        return {"error": f"Invalid status '{status}'. Must be one of: {', '.join(sorted(VALID_BOOKING_STATUSES))}", "booking": None}

    try:
        prop_uuid = uuid.UUID(property_id)
        guest_uuid = uuid.UUID(guest_id)
    except ValueError as e:
        return {"error": f"Invalid UUID: {e}", "booking": None}

    price = None
    if total_price is not None:
        try:
            price = Decimal(total_price)
        except InvalidOperation:
            return {"error": f"Invalid total_price: '{total_price}'", "booking": None}

    try:
        session_factory = get_session_factory()
        async with session_factory() as session:
            # Verify property exists and belongs to user
            prop = await session.get(Property, prop_uuid)
            if prop is None:
                return {"error": f"Property '{property_id}' not found.", "booking": None}
            if user_id and str(prop.owner_id) != user_id:
                return {"error": f"Property '{property_id}' not found.", "booking": None}

            # Verify guest exists
            guest = await session.get(Guest, guest_uuid)
            if guest is None:
                return {"error": f"Guest '{guest_id}' not found.", "booking": None}

            # Check date conflicts
            conflicts = await _check_date_conflict(session, prop_uuid, ci, co)
            if conflicts:
                return {
                    "error": "Date conflict: overlapping booking(s) exist for this property.",
                    "booking": None,
                    "conflicts": [
                        {
                            "booking_id": str(c.id),
                            "check_in": c.check_in.isoformat(),
                            "check_out": c.check_out.isoformat(),
                            "status": c.status,
                        }
                        for c in conflicts
                    ],
                }

            booking = Booking(
                property_id=prop_uuid,
                guest_id=guest_uuid,
                check_in=ci,
                check_out=co,
                num_guests=num_guests,
                status=status,
                total_price=price,
                special_requests=special_requests,
            )
            session.add(booking)
            await session.flush()
            await session.refresh(booking, attribute_names=["property", "guest"])
            await session.commit()

            return {"booking": _serialize_booking(booking)}
    except Exception as e:
        logger.exception("booking_create failed")
        return {"error": str(e), "booking": None}


@mcp.tool()
async def booking_update(
    booking_id: str,
    status: str | None = None,
    check_in: str | None = None,
    check_out: str | None = None,
    num_guests: int | None = None,
    total_price: str | None = None,
    special_requests: str | None = None,
    user_id: str | None = None,
) -> dict:
    """Update an existing booking (modify dates, status, or details).

    Args:
        booking_id: UUID of the booking to update
        status: New status (pending, confirmed, checked_in, checked_out, cancelled)
        check_in: New check-in date (YYYY-MM-DD)
        check_out: New check-out date (YYYY-MM-DD)
        num_guests: Updated number of guests
        total_price: Updated total price
        special_requests: Updated special requests
        user_id: UUID of the current user (verifies property ownership)

    Returns:
        Dict with updated booking details, or error if validation fails.
    """
    try:
        bid = uuid.UUID(booking_id)
    except ValueError as e:
        return {"error": f"Invalid booking_id: {e}", "booking": None}

    if status is not None and status not in VALID_BOOKING_STATUSES:
        return {"error": f"Invalid status '{status}'. Must be one of: {', '.join(sorted(VALID_BOOKING_STATUSES))}", "booking": None}

    try:
        session_factory = get_session_factory()
        async with session_factory() as session:
            result = await session.execute(
                select(Booking)
                .where(Booking.id == bid)
                .options(selectinload(Booking.property), selectinload(Booking.guest))
            )
            booking = result.scalar_one_or_none()
            if booking is None:
                return {"error": f"Booking '{booking_id}' not found.", "booking": None}
            if user_id and booking.property and str(booking.property.owner_id) != user_id:
                return {"error": f"Booking '{booking_id}' not found.", "booking": None}

            # Determine final dates for conflict check
            new_ci = date.fromisoformat(check_in) if check_in else booking.check_in
            new_co = date.fromisoformat(check_out) if check_out else booking.check_out

            if new_co <= new_ci:
                return {"error": "check_out must be after check_in.", "booking": None}

            # If dates changed, check for conflicts
            if check_in or check_out:
                conflicts = await _check_date_conflict(session, booking.property_id, new_ci, new_co, exclude_booking_id=bid)
                if conflicts:
                    return {
                        "error": "Date conflict: overlapping booking(s) exist for this property.",
                        "booking": None,
                        "conflicts": [
                            {
                                "booking_id": str(c.id),
                                "check_in": c.check_in.isoformat(),
                                "check_out": c.check_out.isoformat(),
                                "status": c.status,
                            }
                            for c in conflicts
                        ],
                    }

            # Apply updates
            if check_in:
                booking.check_in = new_ci
            if check_out:
                booking.check_out = new_co
            if status is not None:
                booking.status = status
            if num_guests is not None:
                booking.num_guests = num_guests
            if total_price is not None:
                try:
                    booking.total_price = Decimal(total_price)
                except InvalidOperation:
                    return {"error": f"Invalid total_price: '{total_price}'", "booking": None}
            if special_requests is not None:
                booking.special_requests = special_requests

            session.add(booking)
            await session.flush()
            await session.refresh(booking, attribute_names=["property", "guest"])
            await session.commit()

            return {"booking": _serialize_booking(booking)}
    except Exception as e:
        logger.exception("booking_update failed")
        return {"error": str(e), "booking": None}
