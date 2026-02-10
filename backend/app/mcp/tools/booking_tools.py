"""Booking search MCP tool."""

import logging
import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.mcp import mcp, get_session_factory
from app.models.booking import Booking
from app.models.guest import Guest
from app.models.property import Property

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
