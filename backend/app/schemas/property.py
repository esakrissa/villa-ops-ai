"""Pydantic v2 request/response schemas for property endpoints."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class PropertyCreate(BaseModel):
    """Schema for creating a new property."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    location: str | None = Field(None, max_length=255)
    property_type: str = Field(..., pattern="^(villa|hotel|guesthouse)$")
    max_guests: int | None = Field(None, ge=1)
    base_price_per_night: Decimal | None = Field(None, ge=0)
    amenities: list[str] | None = None
    status: str = Field("active", pattern="^(active|maintenance|inactive)$")


class PropertyUpdate(BaseModel):
    """Schema for partially updating a property. All fields optional."""

    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    location: str | None = Field(None, max_length=255)
    property_type: str | None = Field(None, pattern="^(villa|hotel|guesthouse)$")
    max_guests: int | None = Field(None, ge=1)
    base_price_per_night: Decimal | None = Field(None, ge=0)
    amenities: list[str] | None = None
    status: str | None = Field(None, pattern="^(active|maintenance|inactive)$")


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class PropertyResponse(BaseModel):
    """Public property information returned from the API."""

    id: uuid.UUID
    owner_id: uuid.UUID
    name: str
    description: str | None = None
    location: str | None = None
    property_type: str
    max_guests: int | None = None
    base_price_per_night: Decimal | None = None
    amenities: list | None = None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PropertyListResponse(BaseModel):
    """Paginated list of properties."""

    items: list[PropertyResponse]
    total: int
