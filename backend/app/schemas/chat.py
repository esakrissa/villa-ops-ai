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
    disabled_tools: list[str] = Field(default_factory=list, max_length=200)  # tools switched off in the UI
    model: str | None = Field(default=None, max_length=100)  # model picked in the UI; None = default


class ResumeRequest(BaseModel):
    """Request to resume a paused conversation (HITL confirmation)."""

    action: str = Field(..., pattern="^(approve|cancel)$")  # "approve" or "cancel"
    disabled_tools: list[str] = Field(default_factory=list, max_length=200)
    model: str | None = Field(default=None, max_length=100)


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


class AgentModelResponse(BaseModel):
    """A chat model the user can pick in the composer."""

    id: str  # LiteLLM model id, e.g. "xiaomi_mimo/mimo-v2.6-pro"
    label: str
    default: bool


class AgentToolResponse(BaseModel):
    """A tool the agent can call, for the UI's enable/disable menu."""

    name: str
    description: str
    source: str  # "villaops" or "exa"


class ConversationDetailResponse(BaseModel):
    """Full conversation with messages."""

    id: uuid.UUID
    title: str | None
    created_at: datetime
    updated_at: datetime
    messages: list[MessageResponse]

    model_config = ConfigDict(from_attributes=True)
