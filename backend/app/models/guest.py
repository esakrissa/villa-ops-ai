"""Guest domain model."""

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Guest(Base):
    """Guest model — visitors who book stays at properties."""

    __tablename__ = "guests"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(255), index=True)  # unique per owner, not globally
    phone: Mapped[str | None] = mapped_column(String(50))
    nationality: Mapped[str | None] = mapped_column(String(100))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    # Relationships
    owner: Mapped["User"] = relationship(back_populates="guests", lazy="selectin")  # type: ignore[name-defined]  # noqa: F821
    bookings: Mapped[list["Booking"]] = relationship(  # noqa: F821
        back_populates="guest", lazy="selectin", cascade="all, delete-orphan"
    )

    # Email unique per owner (not globally)
    __table_args__ = (
        UniqueConstraint("owner_id", "email", name="uq_guests_owner_email"),
    )
