"""User model — authentication and profile."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, TimestampMixin, UUIDPrimaryKeyMixin


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """User account for villa/hotel managers."""

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    auth_provider: Mapped[str] = mapped_column(String(50), nullable=False, default="local")
    auth_provider_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    role: Mapped[str] = mapped_column(String(50), default="manager", nullable=False)

    # Relationships
    subscription: Mapped["Subscription | None"] = relationship(
        "Subscription", back_populates="user", uselist=False, lazy="selectin"
    )
    properties: Mapped[list["Property"]] = relationship("Property", back_populates="owner", lazy="selectin")
    conversations: Mapped[list["Conversation"]] = relationship("Conversation", back_populates="user", lazy="selectin")
    llm_usages: Mapped[list["LLMUsage"]] = relationship("LLMUsage", back_populates="user", lazy="selectin")

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r} role={self.role!r}>"
