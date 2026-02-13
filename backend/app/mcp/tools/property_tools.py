"""Property management MCP tool."""

import logging
import uuid
from datetime import date
from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.mcp import get_session_factory, mcp
from app.models.booking import Booking
from app.models.property import Property

logger = logging.getLogger(__name__)

VALID_PROPERTY_STATUSES = {"active", "maintenance", "inactive"}


async def _resolve_property(session, property_id: str | None, property_name: str | None) -> Property | None:
    """Resolve a property by ID or fuzzy name match."""
    if property_id:
        result = await session.execute(
            select(Property).where(Property.id == uuid.UUID(property_id))
        )
        return result.scalar_one_or_none()
    if property_name:
        result = await session.execute(
            select(Property).where(Property.name.ilike(f"%{property_name}%")).limit(1)
        )
        return result.scalar_one_or_none()
    return None


@mcp.tool()
async def property_manage(
    action: str,
    property_id: str | None = None,
    property_name: str | None = None,
    check_in: str | None = None,
    check_out: str | None = None,
    base_price_per_night: str | None = None,
    status: str | None = None,
) -> dict:
    """Manage properties: check availability, update pricing, or change status.

    Args:
        action: One of "check_availability", "update_pricing", "update_status"
        property_id: UUID of the property (can also use property_name)
        property_name: Fuzzy match on property name (alternative to property_id)
        check_in: Start date for availability check (YYYY-MM-DD)
        check_out: End date for availability check (YYYY-MM-DD)
        base_price_per_night: New price per night (for update_pricing action)
        status: New status: active, maintenance, inactive (for update_status action)

    Returns:
        Dict with action result or error details.
    """
    valid_actions = {"check_availability", "update_pricing", "update_status"}
    if action not in valid_actions:
        return {"error": f"Invalid action '{action}'. Must be one of: {', '.join(sorted(valid_actions))}"}

    try:
        session_factory = get_session_factory()
        async with session_factory() as session:
            prop = await _resolve_property(session, property_id, property_name)
            if prop is None:
                return {"error": "Property not found. Provide a valid property_id or property_name."}

            if action == "check_availability":
                return await _check_availability(session, prop, check_in, check_out)
            elif action == "update_pricing":
                return await _update_pricing(session, prop, base_price_per_night)
            else:  # update_status
                return await _update_status(session, prop, status)
    except Exception as e:
        logger.exception("property_manage failed")
        return {"error": str(e)}


async def _check_availability(session, prop: Property, check_in: str | None, check_out: str | None) -> dict:
    """Check if a property is available for the given date range."""
    if not check_in or not check_out:
        return {"error": "check_in and check_out are required for check_availability action."}

    ci = date.fromisoformat(check_in)
    co = date.fromisoformat(check_out)
    if co <= ci:
        return {"error": "check_out must be after check_in."}

    query = select(Booking).where(
        Booking.property_id == prop.id,
        Booking.status != "cancelled",
        Booking.check_in < co,
        Booking.check_out > ci,
    ).options(selectinload(Booking.guest))

    result = await session.execute(query)
    conflicts = list(result.scalars().all())

    return {
        "available": len(conflicts) == 0,
        "property": {
            "id": str(prop.id),
            "name": prop.name,
            "location": prop.location,
            "status": prop.status,
        },
        "dates": {"check_in": check_in, "check_out": check_out},
        "conflicts": [
            {
                "booking_id": str(b.id),
                "guest_name": b.guest.name if b.guest else None,
                "check_in": b.check_in.isoformat(),
                "check_out": b.check_out.isoformat(),
                "status": b.status,
            }
            for b in conflicts
        ],
    }


async def _update_pricing(session, prop: Property, base_price_per_night: str | None) -> dict:
    """Update the base price per night for a property."""
    if not base_price_per_night:
        return {"error": "base_price_per_night is required for update_pricing action."}

    try:
        new_price = Decimal(base_price_per_night)
    except InvalidOperation:
        return {"error": f"Invalid price value: '{base_price_per_night}'. Must be a valid number."}

    if new_price <= 0:
        return {"error": "base_price_per_night must be a positive number."}

    old_price = str(prop.base_price_per_night) if prop.base_price_per_night else None
    prop.base_price_per_night = new_price
    session.add(prop)
    await session.flush()
    await session.refresh(prop)
    await session.commit()

    return {
        "property": {
            "id": str(prop.id),
            "name": prop.name,
            "location": prop.location,
            "status": prop.status,
        },
        "old_price": old_price,
        "new_price": str(prop.base_price_per_night),
    }


async def _update_status(session, prop: Property, status: str | None) -> dict:
    """Update the status of a property."""
    if not status:
        return {"error": "status is required for update_status action."}

    if status not in VALID_PROPERTY_STATUSES:
        return {"error": f"Invalid status '{status}'. Must be one of: {', '.join(sorted(VALID_PROPERTY_STATUSES))}"}

    old_status = prop.status
    prop.status = status
    session.add(prop)
    await session.flush()
    await session.refresh(prop)
    await session.commit()

    return {
        "property": {
            "id": str(prop.id),
            "name": prop.name,
            "location": prop.location,
            "status": prop.status,
        },
        "old_status": old_status,
        "new_status": prop.status,
    }
