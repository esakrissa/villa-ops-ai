"""Guest lookup MCP tool."""

import logging

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.mcp import get_session_factory, mcp
from app.models.booking import Booking
from app.models.guest import Guest

logger = logging.getLogger(__name__)


@mcp.tool()
async def guest_lookup(
    name: str | None = None,
    email: str | None = None,
    include_bookings: bool = True,
    limit: int = 10,
) -> dict:
    """Look up guests by name or email, optionally including their booking history.

    Args:
        name: Fuzzy match on guest name (e.g. "sarah")
        email: Fuzzy match on guest email
        include_bookings: Whether to include each guest's booking history (default True)
        limit: Maximum number of guests returned (default 10)

    Returns:
        Dict with guests list (each with optional bookings), total count, and query filters.
    """
    try:
        session_factory = get_session_factory()
        async with session_factory() as session:
            query = select(Guest)

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
            guests = list(result.scalars().all())

            def serialize_guest(g):
                data = {
                    "id": str(g.id),
                    "name": g.name,
                    "email": g.email,
                    "phone": g.phone,
                    "nationality": g.nationality,
                    "notes": g.notes,
                }
                if include_bookings and g.bookings:
                    data["bookings"] = [
                        {
                            "id": str(b.id),
                            "property_name": b.property.name if b.property else None,
                            "check_in": b.check_in.isoformat(),
                            "check_out": b.check_out.isoformat(),
                            "status": b.status,
                            "total_price": str(b.total_price) if b.total_price else None,
                        }
                        for b in g.bookings
                    ]
                elif include_bookings:
                    data["bookings"] = []
                return data

            return {
                "guests": [serialize_guest(g) for g in guests],
                "total": len(guests),
                "query_filters": {
                    k: v for k, v in {"name": name, "email": email}.items() if v is not None
                },
            }
    except Exception as e:
        logger.exception("guest_lookup failed")
        return {"error": str(e), "guests": [], "total": 0}
