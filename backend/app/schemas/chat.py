"""Pydantic v2 request/response schemas for chat endpoints."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class ChatRequest(BaseModel):
    """Request to send a message to the agent."""

    message: str = Field(..., min_length=1, max_length=10000)
    conversation_id: uuid.UUID | None = None  # None = start new conversation


class ResumeRequest(BaseModel):
    """Request to resume a paused conversation (HITL confirmation)."""

    action: str = Field(..., pattern="^(approve|cancel)$")  # "approve" or "cancel"


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class MessageResponse(BaseModel):
    """A single message in a conversation."""

    id: uuid.UUID
    role: str
    content: str | None
    tool_calls: list[dict[str, Any]] | dict[str, Any] | None = None
    tool_results: dict[str, Any] | None = None
    model_used: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConversationResponse(BaseModel):
    """Summary of a conversation (for listing)."""

    id: uuid.UUID
    title: str | None
    created_at: datetime
    updated_at: datetime
    message_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class ConversationDetailResponse(BaseModel):
    """Full conversation with messages."""

    id: uuid.UUID
    title: str | None
    created_at: datetime
    updated_at: datetime
    messages: list[MessageResponse]

    model_config = ConfigDict(from_attributes=True)
