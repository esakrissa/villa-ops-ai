"""Pydantic v2 request/response schemas for guest endpoints."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class GuestCreate(BaseModel):
    """Schema for creating a new guest."""

    name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr
    phone: str | None = Field(None, max_length=50)
    nationality: str | None = Field(None, max_length=100)
    notes: str | None = None


class GuestUpdate(BaseModel):
    """Schema for partially updating a guest. All fields optional."""

    name: str | None = Field(None, min_length=1, max_length=255)
    email: EmailStr | None = None
    phone: str | None = Field(None, max_length=50)
    nationality: str | None = Field(None, max_length=100)
    notes: str | None = None


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class GuestResponse(BaseModel):
    """Public guest information returned by the API."""

    id: uuid.UUID
    name: str
    email: str
    phone: str | None = None
    nationality: str | None = None
    notes: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class GuestListResponse(BaseModel):
    """Paginated list of guests."""

    items: list[GuestResponse]
    total: int
