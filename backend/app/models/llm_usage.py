"""LLM usage tracking model."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, UUIDPrimaryKeyMixin


class LLMUsage(UUIDPrimaryKeyMixin, Base):
    """Tracks LLM API usage per user for billing and analytics."""

    __tablename__ = "llm_usage"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    model: Mapped[str] = mapped_column(String(255), nullable=False)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    cost: Mapped[float] = mapped_column(Numeric(10, 6), default=0, server_default="0")
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cached: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), index=True)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="llm_usages", lazy="selectin")  # type: ignore[name-defined]  # noqa: F821

    def __repr__(self) -> str:
        return f"<LLMUsage(id={self.id}, user_id={self.user_id}, model={self.model!r}, cost={self.cost})>"
