"""Property model — villas, hotels, and guesthouses."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import JSON, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, UUIDPrimaryKeyMixin


class Property(UUIDPrimaryKeyMixin, Base):
    """A villa, hotel, or guesthouse managed by a user."""

    __tablename__ = "properties"

    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, default=None)
    location: Mapped[str | None] = mapped_column(String(255), default=None)
    property_type: Mapped[str] = mapped_column(String(50), nullable=False)  # villa, hotel, guesthouse
    max_guests: Mapped[int | None] = mapped_column(default=None)
    base_price_per_night: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), default=None)
    amenities: Mapped[dict | None] = mapped_column(JSON, server_default="[]")
    status: Mapped[str] = mapped_column(String(50), server_default="active")  # active, maintenance, inactive
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    # Relationships
    owner: Mapped["User"] = relationship(back_populates="properties", lazy="selectin")  # type: ignore[name-defined]  # noqa: F821
    bookings: Mapped[list["Booking"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        back_populates="property", lazy="selectin", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Property(id={self.id}, name={self.name!r}, type={self.property_type!r})>"
