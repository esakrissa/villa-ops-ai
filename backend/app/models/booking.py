"""Booking model — tracks property reservations."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Index, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, UUIDPrimaryKeyMixin


class Booking(UUIDPrimaryKeyMixin, Base):
    """A reservation linking a guest to a property for specific dates."""

    __tablename__ = "bookings"

    property_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("properties.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    guest_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("guests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    check_in: Mapped[date] = mapped_column(Date, nullable=False)
    check_out: Mapped[date] = mapped_column(Date, nullable=False)
    num_guests: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(
        String(50),
        default="pending",
        index=True,
    )  # pending, confirmed, checked_in, checked_out, cancelled
    total_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    special_requests: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    property: Mapped["Property"] = relationship(back_populates="bookings", lazy="selectin")  # type: ignore[name-defined]  # noqa: F821
    guest: Mapped["Guest"] = relationship(back_populates="bookings", lazy="selectin")  # type: ignore[name-defined]  # noqa: F821

    __table_args__ = (Index("ix_bookings_check_in", "check_in"),)

    def __repr__(self) -> str:
        return (
            f"<Booking(id={self.id}, property_id={self.property_id}, guest_id={self.guest_id}, status={self.status})>"
        )
