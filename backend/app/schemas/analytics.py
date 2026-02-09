"""Pydantic v2 schemas for analytics endpoints."""

import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class OccupancyResponse(BaseModel):
    """Occupancy statistics for a single property over a given period."""

    property_id: uuid.UUID | None = None
    property_name: str | None = None
    period_start: date
    period_end: date
    total_days: int
    booked_days: int
    occupancy_rate: Decimal  # percentage 0.00–100.00


class OccupancySummaryResponse(BaseModel):
    """Aggregated occupancy statistics across all (or filtered) properties."""

    period_start: date
    period_end: date
    properties: list[OccupancyResponse]
    overall_occupancy_rate: Decimal
