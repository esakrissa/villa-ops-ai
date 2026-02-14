"""Property management MCP tools."""

import logging
import uuid
from datetime import date
from decimal import Decimal, InvalidOperation

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.mcp import get_session_factory, mcp
from app.models.booking import Booking
from app.models.property import Property

logger = logging.getLogger(__name__)

VALID_PROPERTY_TYPES = {"villa", "hotel", "guesthouse"}
VALID_PROPERTY_STATUSES = {"active", "maintenance", "inactive"}


def _serialize_property(p: Property) -> dict:
    """Serialize a Property ORM object to a plain dict."""
    return {
        "id": str(p.id),
        "name": p.name,
        "description": p.description,
        "location": p.location,
        "property_type": p.property_type,
        "max_guests": p.max_guests,
        "base_price_per_night": str(p.base_price_per_night) if p.base_price_per_night else None,
        "amenities": p.amenities,
        "status": p.status,
    }


@mcp.tool()
async def property_create(
    name: str,
    property_type: str,
    location: str | None = None,
    description: str | None = None,
    max_guests: int | None = None,
    base_price_per_night: str | None = None,
    amenities: str | None = None,
    user_id: str | None = None,
) -> dict:
    """Create a new property for the current user.

    Args:
        name: Property name (e.g. "Villa Sunrise")
        property_type: One of "villa", "hotel", "guesthouse"
        location: Location description (e.g. "Seminyak, Bali")
        description: Detailed property description (optional)
        max_guests: Maximum guest capacity (optional)
        base_price_per_night: Nightly rate in USD (optional, e.g. "250.00")
        amenities: Comma-separated amenities (optional, e.g. "pool,wifi,kitchen")
        user_id: UUID of the current user (property owner, required)

    Returns:
        Dict with created property details (including UUID) or error.
    """
    if not user_id:
        return {"error": "user_id is required to create a property.", "property": None}
    if not name or not name.strip():
        return {"error": "Property name is required.", "property": None}
    if property_type not in VALID_PROPERTY_TYPES:
        return {
            "error": f"Invalid property_type '{property_type}'. Must be one of: {', '.join(sorted(VALID_PROPERTY_TYPES))}",
            "property": None,
        }

    # Parse price
    parsed_price = None
    if base_price_per_night:
        try:
            parsed_price = Decimal(base_price_per_night)
            if parsed_price <= 0:
                return {"error": "base_price_per_night must be a positive number.", "property": None}
        except InvalidOperation:
            return {"error": f"Invalid price value: '{base_price_per_night}'. Must be a valid number.", "property": None}

    # Parse amenities
    parsed_amenities = []
    if amenities:
        parsed_amenities = [a.strip() for a in amenities.split(",") if a.strip()]

    try:
        owner_uuid = uuid.UUID(user_id)
        session_factory = get_session_factory()
        async with session_factory() as session:
            prop = Property(
                owner_id=owner_uuid,
                name=name.strip(),
                property_type=property_type,
                location=location,
                description=description,
                max_guests=max_guests,
                base_price_per_night=parsed_price,
                amenities=parsed_amenities,
                status="active",
            )
            session.add(prop)
            await session.flush()
            await session.refresh(prop)
            await session.commit()

            logger.info("Property created: %s (owner %s)", prop.name, user_id)
            return {"property": _serialize_property(prop)}
    except Exception as e:
        logger.exception("property_create failed")
        return {"error": str(e), "property": None}


@mcp.tool()
async def property_list(
    status: str | None = None,
    name: str | None = None,
    limit: int = 50,
    user_id: str | None = None,
) -> dict:
    """List properties, optionally filtered by status or name.

    Args:
        status: Filter by property status (active, maintenance, inactive)
        name: Fuzzy match on property name (e.g. "canggu")
        limit: Maximum number of properties returned (default 50)
        user_id: UUID of the current user (filters to only their properties)

    Returns:
        Dict with properties list and total count.
    """
    if status and status not in VALID_PROPERTY_STATUSES:
        return {
            "error": f"Invalid status '{status}'. Must be one of: {', '.join(sorted(VALID_PROPERTY_STATUSES))}",
            "properties": [],
            "total": 0,
        }

    try:
        session_factory = get_session_factory()
        async with session_factory() as session:
            query = select(Property)

            if user_id:
                query = query.where(Property.owner_id == uuid.UUID(user_id))
            if status:
                query = query.where(Property.status == status)
            if name:
                query = query.where(Property.name.ilike(f"%{name}%"))

            query = query.order_by(Property.created_at.desc()).limit(limit)
            result = await session.execute(query)
            properties = list(result.scalars().all())

            return {
                "properties": [
                    {
                        "id": str(p.id),
                        "name": p.name,
                        "location": p.location,
                        "property_type": p.property_type,
                        "max_guests": p.max_guests,
                        "base_price_per_night": str(p.base_price_per_night) if p.base_price_per_night else None,
                        "status": p.status,
                    }
                    for p in properties
                ],
                "total": len(properties),
            }
    except Exception as e:
        logger.exception("property_list failed")
        return {"error": str(e), "properties": [], "total": 0}


@mcp.tool()
async def property_update(
    property_id: str,
    name: str | None = None,
    location: str | None = None,
    description: str | None = None,
    max_guests: int | None = None,
    base_price_per_night: str | None = None,
    amenities: str | None = None,
    status: str | None = None,
    user_id: str | None = None,
) -> dict:
    """Update an existing property. Verifies ownership before updating.

    Args:
        property_id: UUID of the property to update (get from property_list)
        name: Updated property name (optional)
        location: Updated location (optional)
        description: Updated description (optional)
        max_guests: Updated max guest capacity (optional)
        base_price_per_night: Updated nightly rate in USD (optional, e.g. "300.00")
        amenities: Updated comma-separated amenities (optional, replaces existing)
        status: Updated status: active, maintenance, inactive (optional)
        user_id: UUID of the current user (required — verifies ownership)

    Returns:
        Dict with updated property details or error.
    """
    if not user_id:
        return {"error": "user_id is required.", "property": None}

    try:
        pid = uuid.UUID(property_id)
    except ValueError:
        return {"error": f"Invalid property_id: '{property_id}'", "property": None}

    has_update = any([name, location, description, max_guests is not None, base_price_per_night, amenities, status])
    if not has_update:
        return {"error": "At least one field to update must be provided.", "property": None}

    if status and status not in VALID_PROPERTY_STATUSES:
        return {
            "error": f"Invalid status '{status}'. Must be one of: {', '.join(sorted(VALID_PROPERTY_STATUSES))}",
            "property": None,
        }

    # Parse price if provided
    parsed_price = None
    if base_price_per_night:
        try:
            parsed_price = Decimal(base_price_per_night)
            if parsed_price <= 0:
                return {"error": "base_price_per_night must be a positive number.", "property": None}
        except InvalidOperation:
            return {"error": f"Invalid price value: '{base_price_per_night}'.", "property": None}

    try:
        owner_uuid = uuid.UUID(user_id)
        session_factory = get_session_factory()
        async with session_factory() as session:
            result = await session.execute(
                select(Property).where(Property.id == pid, Property.owner_id == owner_uuid)
            )
            prop = result.scalar_one_or_none()
            if prop is None:
                return {"error": f"Property '{property_id}' not found or not owned by you.", "property": None}

            if name is not None:
                prop.name = name.strip()
            if location is not None:
                prop.location = location
            if description is not None:
                prop.description = description
            if max_guests is not None:
                prop.max_guests = max_guests
            if parsed_price is not None:
                prop.base_price_per_night = parsed_price
            if amenities is not None:
                prop.amenities = [a.strip() for a in amenities.split(",") if a.strip()]
            if status is not None:
                prop.status = status

            session.add(prop)
            await session.flush()
            await session.refresh(prop)
            await session.commit()

            logger.info("Property updated: %s (by user %s)", prop.name, user_id)
            return {"property": _serialize_property(prop)}
    except Exception as e:
        logger.exception("property_update failed")
        return {"error": str(e), "property": None}


async def _resolve_property(
    session, property_id: str | None, property_name: str | None, user_id: str | None = None,
) -> Property | None:
    """Resolve a property by ID or fuzzy name match, optionally filtered by owner."""
    if property_id:
        query = select(Property).where(Property.id == uuid.UUID(property_id))
        if user_id:
            query = query.where(Property.owner_id == uuid.UUID(user_id))
        result = await session.execute(query)
        return result.scalar_one_or_none()
    if property_name:
        query = select(Property).where(Property.name.ilike(f"%{property_name}%"))
        if user_id:
            query = query.where(Property.owner_id == uuid.UUID(user_id))
        query = query.limit(1)
        result = await session.execute(query)
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
    user_id: str | None = None,
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
        user_id: UUID of the current user (filters to only their properties)

    Returns:
        Dict with action result or error details.
    """
    valid_actions = {"check_availability", "update_pricing", "update_status"}
    if action not in valid_actions:
        return {"error": f"Invalid action '{action}'. Must be one of: {', '.join(sorted(valid_actions))}"}

    try:
        session_factory = get_session_factory()
        async with session_factory() as session:
            prop = await _resolve_property(session, property_id, property_name, user_id)
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


@mcp.tool()
async def property_delete(
    property_id: str,
    user_id: str | None = None,
) -> dict:
    """Permanently delete a property and all its bookings.

    WARNING: This is a destructive, irreversible operation. All bookings
    associated with this property will be permanently deleted via CASCADE.
    The agent will ask the user for confirmation before executing.

    Args:
        property_id: UUID of the property to delete
        user_id: UUID of the current user (required — verifies ownership)

    Returns:
        Dict with deletion result including counts of deleted items, or error.
    """
    if not user_id:
        return {"error": "user_id is required.", "deleted": False}

    try:
        pid = uuid.UUID(property_id)
    except ValueError:
        return {"error": f"Invalid property_id: '{property_id}'", "deleted": False}

    try:
        owner_uuid = uuid.UUID(user_id)
        session_factory = get_session_factory()
        async with session_factory() as session:
            # Fetch property with ownership check
            result = await session.execute(
                select(Property).where(Property.id == pid, Property.owner_id == owner_uuid)
            )
            prop = result.scalar_one_or_none()
            if prop is None:
                return {"error": f"Property '{property_id}' not found or not owned by you.", "deleted": False}

            # Count associated bookings (for context in response)
            count_result = await session.execute(
                select(func.count()).select_from(Booking).where(Booking.property_id == pid)
            )
            bookings_count = count_result.scalar_one()

            prop_name = prop.name
            prop_location = prop.location

            # Delete (CASCADE removes bookings)
            await session.delete(prop)
            await session.flush()
            await session.commit()

            logger.info(
                "Property deleted: %s (owner %s, %d bookings cascaded)",
                prop_name, user_id, bookings_count,
            )

            return {
                "deleted": True,
                "property_name": prop_name,
                "property_location": prop_location,
                "bookings_deleted": bookings_count,
                "message": f"Property '{prop_name}' and {bookings_count} associated booking(s) permanently deleted.",
            }
    except Exception as e:
        logger.exception("property_delete failed")
        return {"error": str(e), "deleted": False}
