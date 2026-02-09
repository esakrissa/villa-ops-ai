"""Guests CRUD API router.

Guests are shared resources — any authenticated user can create and view guests.
This is intentional because the same guest may book at different managers' properties.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, get_db
from app.models.guest import Guest
from app.models.user import User
from app.schemas.auth import MessageResponse
from app.schemas.guest import (
    GuestCreate,
    GuestListResponse,
    GuestResponse,
    GuestUpdate,
)

router = APIRouter(prefix="/api/v1/guests", tags=["guests"])


@router.post(
    "",
    response_model=GuestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new guest",
)
async def create_guest(
    body: GuestCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Guest:
    """Create a new guest record.

    Raises 409 if a guest with the same email already exists.
    """
    # Check email uniqueness
    existing = await db.execute(select(Guest).where(Guest.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Guest with this email already exists",
        )

    guest = Guest(**body.model_dump())
    db.add(guest)
    await db.flush()
    await db.refresh(guest)
    return guest


@router.get(
    "",
    response_model=GuestListResponse,
    summary="List guests with optional search",
)
async def list_guests(
    search: str | None = Query(None, description="Search by name or email (case-insensitive)"),
    skip: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(20, ge=1, le=100, description="Pagination limit"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """Return a paginated list of guests, optionally filtered by a search term."""
    base_filter = []

    if search:
        search_pattern = f"%{search}%"
        base_filter.append(
            or_(
                Guest.name.ilike(search_pattern),
                Guest.email.ilike(search_pattern),
            )
        )

    # Count total matching guests
    count_query = select(func.count()).select_from(Guest)
    if base_filter:
        count_query = count_query.where(*base_filter)
    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    # Fetch page
    items_query = (
        (select(Guest).where(*base_filter).offset(skip).limit(limit).order_by(Guest.created_at.desc()))
        if base_filter
        else (select(Guest).offset(skip).limit(limit).order_by(Guest.created_at.desc()))
    )
    result = await db.execute(items_query)
    items = list(result.scalars().all())

    return {"items": items, "total": total}


@router.get(
    "/{guest_id}",
    response_model=GuestResponse,
    summary="Get a guest by ID",
)
async def get_guest(
    guest_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Guest:
    """Return a single guest by UUID. Raises 404 if not found."""
    result = await db.execute(select(Guest).where(Guest.id == guest_id))
    guest = result.scalar_one_or_none()

    if guest is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Guest not found",
        )

    return guest


@router.put(
    "/{guest_id}",
    response_model=GuestResponse,
    summary="Update a guest",
)
async def update_guest(
    guest_id: uuid.UUID,
    body: GuestUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Guest:
    """Partially update a guest. Only explicitly provided fields are changed.

    If the email is being changed, checks for uniqueness and raises 409 if taken.
    """
    result = await db.execute(select(Guest).where(Guest.id == guest_id))
    guest = result.scalar_one_or_none()

    if guest is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Guest not found",
        )

    update_data = body.model_dump(exclude_unset=True)

    # If email is being changed, check uniqueness
    if "email" in update_data and update_data["email"] != guest.email:
        existing = await db.execute(select(Guest).where(Guest.email == update_data["email"]))
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Guest with this email already exists",
            )

    for field, value in update_data.items():
        setattr(guest, field, value)

    db.add(guest)
    await db.flush()
    await db.refresh(guest)
    return guest


@router.delete(
    "/{guest_id}",
    response_model=MessageResponse,
    summary="Delete a guest",
)
async def delete_guest(
    guest_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """Delete a guest by UUID. Cascades to associated bookings.

    Raises 404 if the guest does not exist.
    """
    result = await db.execute(select(Guest).where(Guest.id == guest_id))
    guest = result.scalar_one_or_none()

    if guest is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Guest not found",
        )

    await db.delete(guest)
    await db.flush()
    return {"message": "Guest deleted"}
