"""Bookings CRUD API router.

Ownership rule: a user can only access bookings that belong to **their**
properties.  Every booking query filters through ``Property.owner_id``.
"""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_active_user, get_db
from app.models.booking import Booking
from app.models.guest import Guest
from app.models.property import Property
from app.models.user import User
from app.schemas.auth import MessageResponse
from app.schemas.booking import (
    BookingCreate,
    BookingDetailResponse,
    BookingListResponse,
    BookingResponse,
    BookingUpdate,
)

router = APIRouter(prefix="/api/v1/bookings", tags=["bookings"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_booking_with_ownership(
    booking_id: uuid.UUID,
    current_user: User,
    db: AsyncSession,
) -> Booking:
    """Fetch a booking and verify the user owns the associated property.

    Raises ``HTTPException 404`` when the booking does not exist or does not
    belong to a property owned by the current user.
    """
    result = await db.execute(
        select(Booking)
        .join(Property, Booking.property_id == Property.id)
        .where(Booking.id == booking_id, Property.owner_id == current_user.id)
    )
    booking = result.scalar_one_or_none()

    if booking is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found",
        )
    return booking


async def _check_date_conflict(
    db: AsyncSession,
    property_id: uuid.UUID,
    check_in: date,
    check_out: date,
    exclude_booking_id: uuid.UUID | None = None,
) -> None:
    """Raise 409 if there is an overlapping non-cancelled booking."""
    query = select(Booking).where(
        Booking.property_id == property_id,
        Booking.status != "cancelled",
        Booking.check_in < check_out,
        Booking.check_out > check_in,
    )
    if exclude_booking_id is not None:
        query = query.where(Booking.id != exclude_booking_id)

    result = await db.execute(query)
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Dates conflict with an existing booking",
        )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "",
    response_model=BookingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new booking",
)
async def create_booking(
    body: BookingCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Booking:
    """Create a booking for a property owned by the current user.

    Validates that:
    - The property belongs to the current user.
    - The guest exists.
    - There are no date conflicts with existing non-cancelled bookings.
    """
    # Verify property ownership
    prop_result = await db.execute(
        select(Property).where(
            Property.id == body.property_id,
            Property.owner_id == current_user.id,
        )
    )
    if prop_result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property not found",
        )

    # Verify guest exists
    guest_result = await db.execute(select(Guest).where(Guest.id == body.guest_id))
    if guest_result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Guest not found",
        )

    # Check for date conflicts
    await _check_date_conflict(db, body.property_id, body.check_in, body.check_out)

    # Create the booking
    booking = Booking(**body.model_dump())
    db.add(booking)
    await db.flush()
    await db.refresh(booking)
    return booking


@router.get(
    "",
    response_model=BookingListResponse,
    summary="List bookings for the current user's properties",
)
async def list_bookings(
    property_id: uuid.UUID | None = Query(None, description="Filter by property"),
    guest_id: uuid.UUID | None = Query(None, description="Filter by guest"),
    status_filter: str | None = Query(None, alias="status", description="Filter by booking status"),
    check_in_from: date | None = Query(None, description="Bookings with check_in >= this date"),
    check_in_to: date | None = Query(None, description="Bookings with check_in <= this date"),
    skip: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(20, ge=1, le=100, description="Pagination limit"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """Return a paginated list of bookings for properties owned by the user."""
    # Base filter: only bookings on the current user's properties
    base_query = (
        select(Booking).join(Property, Booking.property_id == Property.id).where(Property.owner_id == current_user.id)
    )
    count_query = (
        select(func.count())
        .select_from(Booking)
        .join(Property, Booking.property_id == Property.id)
        .where(Property.owner_id == current_user.id)
    )

    # Dynamic filters
    if property_id is not None:
        base_query = base_query.where(Booking.property_id == property_id)
        count_query = count_query.where(Booking.property_id == property_id)
    if guest_id is not None:
        base_query = base_query.where(Booking.guest_id == guest_id)
        count_query = count_query.where(Booking.guest_id == guest_id)
    if status_filter is not None:
        base_query = base_query.where(Booking.status == status_filter)
        count_query = count_query.where(Booking.status == status_filter)
    if check_in_from is not None:
        base_query = base_query.where(Booking.check_in >= check_in_from)
        count_query = count_query.where(Booking.check_in >= check_in_from)
    if check_in_to is not None:
        base_query = base_query.where(Booking.check_in <= check_in_to)
        count_query = count_query.where(Booking.check_in <= check_in_to)

    # Total count
    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    # Fetch page
    items_query = base_query.order_by(Booking.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(items_query)
    items = list(result.scalars().all())

    return {"items": items, "total": total}


@router.get(
    "/{booking_id}",
    response_model=BookingDetailResponse,
    summary="Get booking detail with nested property and guest",
)
async def get_booking(
    booking_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Booking:
    """Retrieve a single booking with nested property and guest objects.

    Returns 404 if the booking doesn't exist or isn't on a property owned by
    the current user.
    """
    result = await db.execute(
        select(Booking)
        .options(selectinload(Booking.property), selectinload(Booking.guest))
        .join(Property, Booking.property_id == Property.id)
        .where(Booking.id == booking_id, Property.owner_id == current_user.id)
    )
    booking = result.scalar_one_or_none()

    if booking is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found",
        )
    return booking


@router.put(
    "/{booking_id}",
    response_model=BookingResponse,
    summary="Update a booking",
)
async def update_booking(
    booking_id: uuid.UUID,
    body: BookingUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Booking:
    """Partially update a booking.

    Re-runs date conflict detection when dates change. If ``property_id`` is
    being changed, verifies that the new property is also owned by the user.
    """
    booking = await _get_booking_with_ownership(booking_id, current_user, db)

    update_data = body.model_dump(exclude_unset=True)

    # If property_id is being changed, verify new property ownership
    if "property_id" in update_data and update_data["property_id"] != booking.property_id:
        new_prop_result = await db.execute(
            select(Property).where(
                Property.id == update_data["property_id"],
                Property.owner_id == current_user.id,
            )
        )
        if new_prop_result.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Property not found",
            )

    # If guest_id is being changed, verify new guest exists
    if "guest_id" in update_data and update_data["guest_id"] != booking.guest_id:
        guest_result = await db.execute(select(Guest).where(Guest.id == update_data["guest_id"]))
        if guest_result.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Guest not found",
            )

    # Determine effective dates and property for conflict check
    effective_check_in = update_data.get("check_in", booking.check_in)
    effective_check_out = update_data.get("check_out", booking.check_out)
    effective_property_id = update_data.get("property_id", booking.property_id)

    # Re-run date conflict check if any date or property changed
    dates_changed = "check_in" in update_data or "check_out" in update_data
    property_changed = "property_id" in update_data and update_data["property_id"] != booking.property_id

    if dates_changed or property_changed:
        await _check_date_conflict(
            db,
            effective_property_id,
            effective_check_in,
            effective_check_out,
            exclude_booking_id=booking.id,
        )

    # Apply updates
    for field, value in update_data.items():
        setattr(booking, field, value)

    db.add(booking)
    await db.flush()
    await db.refresh(booking)
    return booking


@router.delete(
    "/{booking_id}",
    response_model=MessageResponse,
    summary="Delete a booking",
)
async def delete_booking(
    booking_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """Delete a booking. Only bookings on properties owned by the user can be deleted."""
    booking = await _get_booking_with_ownership(booking_id, current_user, db)

    await db.delete(booking)
    await db.flush()
    return {"message": "Booking deleted"}
