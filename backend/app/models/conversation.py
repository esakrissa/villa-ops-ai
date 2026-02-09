"""Conversation and Message models for chat history."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, Index, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Conversation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A chat conversation belonging to a user."""

    __tablename__ = "conversations"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str | None] = mapped_column(String(500))

    # Relationships
    user: Mapped["User"] = relationship(back_populates="conversations", lazy="selectin")  # type: ignore[name-defined]  # noqa: F821
    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation",
        lazy="selectin",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )

    __table_args__ = (Index("ix_conversations_user_id_created_at", "user_id", "created_at"),)

    def __repr__(self) -> str:
        return f"<Conversation(id={self.id}, user_id={self.user_id}, title={self.title!r})>"


class Message(UUIDPrimaryKeyMixin, Base):
    """A single message within a conversation. Messages are immutable (no updated_at)."""

    __tablename__ = "messages"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(50), nullable=False)  # 'user', 'assistant', 'tool'
    content: Mapped[str | None] = mapped_column(Text)
    tool_calls: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=None)
    tool_results: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=None)
    model_used: Mapped[str | None] = mapped_column(String(100))
    tokens_used: Mapped[int | None] = mapped_column()
    cost: Mapped[float | None] = mapped_column(Numeric(10, 6))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    # Relationships
    conversation: Mapped["Conversation"] = relationship(back_populates="messages", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Message(id={self.id}, conversation_id={self.conversation_id}, role={self.role!r})>"
