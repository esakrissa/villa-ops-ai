"""Guest MCP tools — lookup, create, update, and delete guests."""

import logging
import uuid as uuid_mod

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.mcp import get_session_factory, mcp
from app.models.booking import Booking
from app.models.guest import Guest

logger = logging.getLogger(__name__)


def _serialize_guest(g: Guest, include_bookings: bool = False) -> dict:
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


@mcp.tool()
async def guest_lookup(
    name: str | None = None,
    email: str | None = None,
    include_bookings: bool = True,
    limit: int = 10,
    user_id: str | None = None,
) -> dict:
    """Look up guests by name or email. Only returns guests owned by the current user.

    Args:
        name: Fuzzy match on guest name (e.g. "sarah")
        email: Fuzzy match on guest email
        include_bookings: Whether to include each guest's booking history (default True)
        limit: Maximum number of guests returned (default 10)
        user_id: UUID of the current user (required — filters to their guests only)

    Returns:
        Dict with guests list (each with optional bookings), total count, and query filters.
    """
    if not user_id:
        return {"error": "user_id is required.", "guests": [], "total": 0}

    try:
        owner_uuid = uuid_mod.UUID(user_id)
        session_factory = get_session_factory()
        async with session_factory() as session:
            query = select(Guest).where(Guest.owner_id == owner_uuid)

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

            return {
                "guests": [_serialize_guest(g, include_bookings) for g in guests],
                "total": len(guests),
                "query_filters": {
                    k: v for k, v in {"name": name, "email": email}.items() if v is not None
                },
            }
    except Exception as e:
        logger.exception("guest_lookup failed")
        return {"error": str(e), "guests": [], "total": 0}


@mcp.tool()
async def guest_create(
    name: str,
    email: str,
    phone: str | None = None,
    nationality: str | None = None,
    notes: str | None = None,
    user_id: str | None = None,
) -> dict:
    """Create a new guest record owned by the current user.

    Use this when a guest doesn't exist in the system and needs to be created
    before a booking can be made. Call guest_lookup first to check if the guest
    already exists.

    Args:
        name: Full name of the guest
        email: Email address (must be unique per owner)
        phone: Phone number (optional)
        nationality: Nationality (optional)
        notes: Additional notes about the guest (optional)
        user_id: UUID of the current user (required — sets owner_id)

    Returns:
        Dict with created guest details (including UUID) or error.
    """
    if not user_id:
        return {"error": "user_id is required to create a guest.", "guest": None}
    if not name or not name.strip():
        return {"error": "Guest name is required.", "guest": None}
    if not email or not email.strip():
        return {"error": "Guest email is required.", "guest": None}

    try:
        owner_uuid = uuid_mod.UUID(user_id)
        session_factory = get_session_factory()
        async with session_factory() as session:
            # Check for existing guest with same email for this owner
            result = await session.execute(
                select(Guest).where(
                    Guest.email.ilike(email.strip()),
                    Guest.owner_id == owner_uuid,
                )
            )
            existing = result.scalar_one_or_none()
            if existing:
                return {
                    "guest": _serialize_guest(existing),
                    "already_existed": True,
                    "message": f"Guest with email '{email}' already exists.",
                }

            guest = Guest(
                owner_id=owner_uuid,
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
                "Guest created: %s <%s> (owner %s)",
                guest.name, guest.email, user_id,
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
    """Update an existing guest's details. Verifies ownership before updating.

    Args:
        guest_id: UUID of the guest to update (get from guest_lookup or guest_create)
        name: Updated full name (optional)
        email: Updated email address (optional, must be unique per owner)
        phone: Updated phone number (optional)
        nationality: Updated nationality (optional)
        notes: Updated notes (optional)
        user_id: UUID of the current user (required — verifies ownership)

    Returns:
        Dict with updated guest details or error.
    """
    if not user_id:
        return {"error": "user_id is required.", "guest": None}

    try:
        gid = uuid_mod.UUID(guest_id)
    except ValueError:
        return {"error": f"Invalid guest_id: '{guest_id}'", "guest": None}

    if not any([name, email, phone, nationality, notes]):
        return {"error": "At least one field to update must be provided.", "guest": None}

    try:
        owner_uuid = uuid_mod.UUID(user_id)
        session_factory = get_session_factory()
        async with session_factory() as session:
            # Fetch guest with ownership check
            result = await session.execute(
                select(Guest).where(Guest.id == gid, Guest.owner_id == owner_uuid)
            )
            guest = result.scalar_one_or_none()
            if guest is None:
                return {"error": f"Guest '{guest_id}' not found or not owned by you.", "guest": None}

            # Check email uniqueness scoped to owner if changing email
            if email and email.strip().lower() != guest.email.lower():
                dup_result = await session.execute(
                    select(Guest).where(
                        Guest.email.ilike(email.strip()),
                        Guest.owner_id == owner_uuid,
                        Guest.id != gid,
                    )
                )
                existing = dup_result.scalar_one_or_none()
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
                guest.name, guest.email, user_id,
            )

            return {"guest": _serialize_guest(guest)}
    except Exception as e:
        logger.exception("guest_update failed")
        return {"error": str(e), "guest": None}


@mcp.tool()
async def guest_delete(
    guest_id: str,
    user_id: str | None = None,
) -> dict:
    """Permanently delete a guest and all their bookings.

    WARNING: This is a destructive, irreversible operation. All bookings
    associated with this guest will be permanently deleted via CASCADE.
    The agent will ask the user for confirmation before executing.

    Args:
        guest_id: UUID of the guest to delete
        user_id: UUID of the current user (required — verifies ownership)

    Returns:
        Dict with deletion result including counts of deleted items, or error.
    """
    if not user_id:
        return {"error": "user_id is required.", "deleted": False}

    try:
        gid = uuid_mod.UUID(guest_id)
    except ValueError:
        return {"error": f"Invalid guest_id: '{guest_id}'", "deleted": False}

    try:
        owner_uuid = uuid_mod.UUID(user_id)
        session_factory = get_session_factory()
        async with session_factory() as session:
            # Fetch guest with ownership check
            result = await session.execute(
                select(Guest).where(Guest.id == gid, Guest.owner_id == owner_uuid)
            )
            guest = result.scalar_one_or_none()
            if guest is None:
                return {"error": f"Guest '{guest_id}' not found or not owned by you.", "deleted": False}

            # Count associated bookings (for context in response)
            count_result = await session.execute(
                select(func.count()).select_from(Booking).where(Booking.guest_id == gid)
            )
            bookings_count = count_result.scalar_one()

            guest_name = guest.name
            guest_email = guest.email

            # Delete (CASCADE removes bookings)
            await session.delete(guest)
            await session.flush()
            await session.commit()

            logger.info(
                "Guest deleted: %s <%s> (owner %s, %d bookings cascaded)",
                guest_name, guest_email, user_id, bookings_count,
            )

            return {
                "deleted": True,
                "guest_name": guest_name,
                "guest_email": guest_email,
                "bookings_deleted": bookings_count,
                "message": f"Guest '{guest_name}' and {bookings_count} associated booking(s) permanently deleted.",
            }
    except Exception as e:
        logger.exception("guest_delete failed")
        return {"error": str(e), "deleted": False}
