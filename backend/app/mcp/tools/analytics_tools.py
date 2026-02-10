"""Booking analytics MCP tool — occupancy, revenue, and trends."""

import logging
import uuid
from collections import defaultdict
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.mcp import mcp, get_session_factory
from app.models.booking import Booking
from app.models.property import Property

logger = logging.getLogger(__name__)


def _calculate_occupancy(
    bookings: list[Booking],
    period_start: date,
    period_end: date,
) -> tuple[int, int]:
    """Calculate booked days within a period, avoiding double-counting overlaps.

    Returns (total_days, booked_days).
    """
    total_days = (period_end - period_start).days
    if total_days <= 0:
        return 0, 0

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


@mcp.tool()
async def booking_analytics(
    property_name: str | None = None,
    property_id: str | None = None,
    period_start: str | None = None,
    period_end: str | None = None,
    metric: str = "summary",
) -> dict:
    """Analyze booking performance: occupancy, revenue, and trends.

    Args:
        property_name: Filter by property name (fuzzy match)
        property_id: Filter by exact property UUID
        period_start: Start date for analysis (YYYY-MM-DD, defaults to 30 days ago)
        period_end: End date for analysis (YYYY-MM-DD, defaults to today)
        metric: Type of analysis — "summary" (all), "occupancy", "revenue", or "trends"

    Returns:
        Dict with analytics results based on the requested metric.
    """
    valid_metrics = {"summary", "occupancy", "revenue", "trends"}
    if metric not in valid_metrics:
        return {"error": f"Invalid metric '{metric}'. Must be one of: {', '.join(sorted(valid_metrics))}"}

    today = date.today()
    try:
        p_start = date.fromisoformat(period_start) if period_start else today - timedelta(days=30)
        p_end = date.fromisoformat(period_end) if period_end else today
    except ValueError as e:
        return {"error": f"Invalid date format: {e}"}

    if p_end <= p_start:
        return {"error": "period_end must be after period_start."}

    try:
        session_factory = get_session_factory()
        async with session_factory() as session:
            # Fetch properties
            prop_query = select(Property)
            if property_name:
                prop_query = prop_query.where(Property.name.ilike(f"%{property_name}%"))
            if property_id:
                prop_query = prop_query.where(Property.id == uuid.UUID(property_id))

            prop_result = await session.execute(prop_query)
            properties = list(prop_result.scalars().all())

            if not properties:
                return {
                    "error": "No properties found matching the filter.",
                    "period": {"start": p_start.isoformat(), "end": p_end.isoformat()},
                }

            property_ids = [p.id for p in properties]

            # Fetch non-cancelled bookings overlapping the period
            bookings_query = (
                select(Booking)
                .where(
                    Booking.property_id.in_(property_ids),
                    Booking.status != "cancelled",
                    Booking.check_in < p_end,
                    Booking.check_out > p_start,
                )
                .options(selectinload(Booking.property))
            )
            bookings_result = await session.execute(bookings_query)
            all_bookings = list(bookings_result.scalars().all())

            # Group bookings by property
            bookings_by_property: dict[uuid.UUID, list[Booking]] = defaultdict(list)
            for b in all_bookings:
                bookings_by_property[b.property_id].append(b)

            result: dict = {
                "period": {"start": p_start.isoformat(), "end": p_end.isoformat()},
                "properties_analyzed": len(properties),
            }

            # Occupancy
            if metric in ("summary", "occupancy"):
                result["occupancy"] = _build_occupancy(properties, bookings_by_property, p_start, p_end)

            # Revenue
            if metric in ("summary", "revenue"):
                result["revenue"] = _build_revenue(all_bookings, bookings_by_property, p_start, p_end)

            # Trends
            if metric in ("summary", "trends"):
                result["trends"] = await _build_trends(
                    session, property_ids, p_start, p_end,
                )

            return result
    except Exception as e:
        logger.exception("booking_analytics failed")
        return {"error": str(e)}


def _build_occupancy(
    properties: list[Property],
    bookings_by_property: dict[uuid.UUID, list[Booking]],
    p_start: date,
    p_end: date,
) -> dict:
    """Build occupancy metrics."""
    per_property = []
    total_booked_sum = 0
    total_days_sum = 0

    for prop in properties:
        prop_bookings = bookings_by_property.get(prop.id, [])
        total_days, booked_days = _calculate_occupancy(prop_bookings, p_start, p_end)

        if total_days > 0:
            rate = Decimal(booked_days * 100) / Decimal(total_days)
            rate = rate.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        else:
            rate = Decimal("0.00")

        per_property.append({
            "name": prop.name,
            "property_id": str(prop.id),
            "total_days": total_days,
            "booked_days": booked_days,
            "rate": str(rate),
        })

        total_booked_sum += booked_days
        total_days_sum += total_days

    if total_days_sum > 0:
        overall_rate = Decimal(total_booked_sum * 100) / Decimal(total_days_sum)
        overall_rate = overall_rate.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    else:
        overall_rate = Decimal("0.00")

    return {
        "total_days": (p_end - p_start).days,
        "booked_days": total_booked_sum,
        "occupancy_rate": str(overall_rate),
        "per_property": per_property,
    }


def _build_revenue(
    all_bookings: list[Booking],
    bookings_by_property: dict[uuid.UUID, list[Booking]],
    p_start: date,
    p_end: date,
) -> dict:
    """Build revenue metrics."""
    total_revenue = Decimal("0.00")
    by_status: dict[str, int] = defaultdict(int)

    for b in all_bookings:
        if b.total_price:
            total_revenue += b.total_price
        by_status[b.status] += 1

    # Total booked nights across all properties
    total_booked_nights = 0
    for prop_bookings in bookings_by_property.values():
        for b in prop_bookings:
            overlap_start = max(b.check_in, p_start)
            overlap_end = min(b.check_out, p_end)
            if overlap_start < overlap_end:
                total_booked_nights += (overlap_end - overlap_start).days

    if total_booked_nights > 0:
        adr = (total_revenue / Decimal(total_booked_nights)).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
    else:
        adr = Decimal("0.00")

    return {
        "total_revenue": str(total_revenue.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
        "average_daily_rate": str(adr),
        "booking_count": len(all_bookings),
        "by_status": dict(by_status),
    }


async def _build_trends(
    session,
    property_ids: list[uuid.UUID],
    p_start: date,
    p_end: date,
) -> dict:
    """Build trends: current vs previous period comparison."""
    period_length = (p_end - p_start).days
    prev_start = p_start - timedelta(days=period_length)
    prev_end = p_start

    # Current period booking count (already fetched, but count via query for accuracy)
    current_query = select(Booking).where(
        Booking.property_id.in_(property_ids),
        Booking.status != "cancelled",
        Booking.check_in < p_end,
        Booking.check_out > p_start,
    )
    current_result = await session.execute(current_query)
    current_count = len(list(current_result.scalars().all()))

    # Previous period booking count
    prev_query = select(Booking).where(
        Booking.property_id.in_(property_ids),
        Booking.status != "cancelled",
        Booking.check_in < prev_end,
        Booking.check_out > prev_start,
    )
    prev_result = await session.execute(prev_query)
    prev_count = len(list(prev_result.scalars().all()))

    if prev_count > 0:
        change = Decimal((current_count - prev_count) * 100) / Decimal(prev_count)
        change = change.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    else:
        change = Decimal("100.00") if current_count > 0 else Decimal("0.00")

    return {
        "current_period_bookings": current_count,
        "previous_period_bookings": prev_count,
        "change_percentage": str(change),
    }
