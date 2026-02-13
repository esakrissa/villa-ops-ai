"""Pydantic v2 request/response schemas for booking endpoints."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.guest import GuestResponse
from app.schemas.property import PropertyResponse

# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class BookingCreate(BaseModel):
    """Schema for creating a new booking."""

    property_id: uuid.UUID
    guest_id: uuid.UUID
    check_in: date
    check_out: date
    num_guests: int = Field(1, ge=1)
    status: str = Field("pending", pattern="^(pending|confirmed)$")
    total_price: Decimal | None = Field(None, ge=0)
    special_requests: str | None = None

    @model_validator(mode="after")
    def check_dates(self) -> "BookingCreate":
        """Validate that check_out is strictly after check_in."""
        if self.check_out <= self.check_in:
            raise ValueError("check_out must be after check_in")
        return self


class BookingUpdate(BaseModel):
    """Schema for partially updating a booking. All fields optional."""

    property_id: uuid.UUID | None = None
    guest_id: uuid.UUID | None = None
    check_in: date | None = None
    check_out: date | None = None
    num_guests: int | None = Field(None, ge=1)
    status: str | None = Field(
        None,
        pattern="^(pending|confirmed|checked_in|checked_out|cancelled)$",
    )
    total_price: Decimal | None = Field(None, ge=0)
    special_requests: str | None = None

    @model_validator(mode="after")
    def check_dates(self) -> "BookingUpdate":
        """If both dates are provided, validate check_out > check_in."""
        if self.check_in is not None and self.check_out is not None and self.check_out <= self.check_in:
            raise ValueError("check_out must be after check_in")
        return self


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class BookingResponse(BaseModel):
    """Standard booking response returned from CRUD operations."""

    id: uuid.UUID
    property_id: uuid.UUID
    guest_id: uuid.UUID
    check_in: date
    check_out: date
    num_guests: int
    status: str
    total_price: Decimal | None = None
    special_requests: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BookingDetailResponse(BookingResponse):
    """Extended booking response with nested property and guest details.

    Used for single-booking detail views where the client needs the full
    context without extra round-trips.
    """

    property: PropertyResponse | None = None
    guest: GuestResponse | None = None


class BookingListResponse(BaseModel):
    """Paginated list of bookings."""

    items: list[BookingResponse]
    total: int
