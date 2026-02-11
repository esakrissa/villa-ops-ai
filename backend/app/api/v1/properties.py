"""Properties CRUD API routes — ownership-scoped."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import check_property_limit, get_current_active_user, get_db
from app.models.property import Property
from app.models.user import User
from app.schemas.auth import MessageResponse
from app.schemas.property import (
    PropertyCreate,
    PropertyListResponse,
    PropertyResponse,
    PropertyUpdate,
)

router = APIRouter(prefix="/api/v1/properties", tags=["properties"])


@router.post(
    "",
    response_model=PropertyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new property",
)
async def create_property(
    body: PropertyCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _limit_check: None = Depends(check_property_limit),  # Plan gating
) -> PropertyResponse:
    """Create a property owned by the authenticated user."""
    prop = Property(
        owner_id=current_user.id,
        **body.model_dump(),
    )
    db.add(prop)
    await db.flush()
    await db.refresh(prop)
    return PropertyResponse.model_validate(prop)


@router.get(
    "",
    response_model=PropertyListResponse,
    summary="List properties owned by the current user",
)
async def list_properties(
    status_filter: str | None = Query(None, alias="status"),
    property_type: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> PropertyListResponse:
    """Return paginated properties belonging to the current user."""
    base_filter = Property.owner_id == current_user.id

    # Build dynamic filters
    filters = [base_filter]
    if status_filter is not None:
        filters.append(Property.status == status_filter)
    if property_type is not None:
        filters.append(Property.property_type == property_type)

    # Total count
    count_query = select(func.count()).select_from(Property).where(*filters)
    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    # Fetch page
    items_query = select(Property).where(*filters).order_by(Property.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(items_query)
    items = list(result.scalars().all())

    return PropertyListResponse(
        items=[PropertyResponse.model_validate(p) for p in items],
        total=total,
    )


@router.get(
    "/{property_id}",
    response_model=PropertyResponse,
    summary="Get a property by ID",
)
async def get_property(
    property_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> PropertyResponse:
    """Retrieve a single property. Returns 404 if not found or not owned."""
    result = await db.execute(select(Property).where(Property.id == property_id))
    prop = result.scalar_one_or_none()

    if prop is None or prop.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property not found",
        )

    return PropertyResponse.model_validate(prop)


@router.put(
    "/{property_id}",
    response_model=PropertyResponse,
    summary="Update a property",
)
async def update_property(
    property_id: uuid.UUID,
    body: PropertyUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> PropertyResponse:
    """Partially update a property. Only explicitly set fields are changed."""
    result = await db.execute(select(Property).where(Property.id == property_id))
    prop = result.scalar_one_or_none()

    if prop is None or prop.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property not found",
        )

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(prop, field, value)

    db.add(prop)
    await db.flush()
    await db.refresh(prop)

    return PropertyResponse.model_validate(prop)


@router.delete(
    "/{property_id}",
    response_model=MessageResponse,
    summary="Delete a property",
)
async def delete_property(
    property_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> MessageResponse:
    """Delete a property and cascade-delete its bookings."""
    result = await db.execute(select(Property).where(Property.id == property_id))
    prop = result.scalar_one_or_none()

    if prop is None or prop.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property not found",
        )

    await db.delete(prop)
    await db.flush()

    return MessageResponse(message="Property deleted")
