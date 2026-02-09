"""Analytics API router — occupancy rates and property performance metrics."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, get_db
from app.models.booking import Booking
from app.models.property import Property
from app.models.user import User
from app.schemas.analytics import OccupancyResponse, OccupancySummaryResponse

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


def _calculate_occupancy(
    bookings: list[Booking],
    period_start: date,
    period_end: date,
) -> tuple[int, int]:
    """Calculate booked days within a period, avoiding double-counting overlaps.

    Returns:
        A tuple of (total_days, booked_days).
    """
    total_days = (period_end - period_start).days
    if total_days <= 0:
        return 0, 0

    # Use a set of dates to avoid double-counting when bookings overlap
    booked_dates: set[date] = set()
    for booking in bookings:
        overlap_start = max(booking.check_in, period_start)
        overlap_end = min(booking.check_out, period_end)
        if overlap_start < overlap_end:
            day = overlap_start
            while day < overlap_end:
                booked_dates.add(day)
                day = date.fromordinal(day.toordinal() + 1)

    return total_days, len(booked_dates)


@router.get("/occupancy", response_model=OccupancySummaryResponse)
async def get_occupancy(
    period_start: date = Query(..., description="Start of the analysis period"),
    period_end: date = Query(..., description="End of the analysis period"),
    property_id: uuid.UUID | None = Query(None, description="Filter by specific property"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> OccupancySummaryResponse:
    """Calculate occupancy rates for the authenticated user's properties.

    For each property the endpoint computes how many days within the requested
    period are covered by non-cancelled bookings.  An overall weighted average
    is returned alongside per-property breakdowns.
    """
    if period_end <= period_start:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="period_end must be after period_start",
        )

    # Fetch properties owned by the current user
    properties_query = select(Property).where(Property.owner_id == current_user.id)
    if property_id is not None:
        properties_query = properties_query.where(Property.id == property_id)

    properties_result = await db.execute(properties_query)
    properties = list(properties_result.scalars().all())

    if not properties and property_id is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property not found",
        )

    property_ids = [p.id for p in properties]

    # Fetch all non-cancelled bookings that overlap the period for these properties
    bookings_query = select(Booking).where(
        Booking.property_id.in_(property_ids),
        Booking.status != "cancelled",
        Booking.check_in < period_end,
        Booking.check_out > period_start,
    )
    bookings_result = await db.execute(bookings_query)
    all_bookings = list(bookings_result.scalars().all())

    # Group bookings by property
    bookings_by_property: dict[uuid.UUID, list[Booking]] = {pid: [] for pid in property_ids}
    for booking in all_bookings:
        bookings_by_property[booking.property_id].append(booking)

    # Calculate per-property occupancy
    occupancy_items: list[OccupancyResponse] = []
    total_booked_sum = 0
    total_days_sum = 0

    for prop in properties:
        prop_bookings = bookings_by_property.get(prop.id, [])
        total_days, booked_days = _calculate_occupancy(prop_bookings, period_start, period_end)

        if total_days > 0:
            rate = Decimal(booked_days * 100) / Decimal(total_days)
            rate = rate.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        else:
            rate = Decimal("0.00")

        occupancy_items.append(
            OccupancyResponse(
                property_id=prop.id,
                property_name=prop.name,
                period_start=period_start,
                period_end=period_end,
                total_days=total_days,
                booked_days=booked_days,
                occupancy_rate=rate,
            )
        )

        total_booked_sum += booked_days
        total_days_sum += total_days

    # Overall occupancy rate (weighted average across all properties)
    if total_days_sum > 0:
        overall_rate = Decimal(total_booked_sum * 100) / Decimal(total_days_sum)
        overall_rate = overall_rate.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    else:
        overall_rate = Decimal("0.00")

    return OccupancySummaryResponse(
        period_start=period_start,
        period_end=period_end,
        properties=occupancy_items,
        overall_occupancy_rate=overall_rate,
    )
