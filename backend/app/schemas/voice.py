"""Schemas for voice mode (Villa)."""

import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field


class VoiceModel(BaseModel):
    id: str
    label: str
    default: bool = False


class VoiceConfigResponse(BaseModel):
    enabled: bool
    agent_name: str
    models: list[VoiceModel]
    voice: str


class VoiceSessionRequest(BaseModel):
    # Continue an existing chat by voice; omit to start a new conversation
    conversation_id: uuid.UUID | None = None
    model: str | None = None
    # Tools the user switched off in the composer's tools menu
    disabled_tools: list[str] = Field(default_factory=list, max_length=100)


class VoiceSessionResponse(BaseModel):
    server_url: str
    participant_token: str
    room_name: str
    conversation_id: uuid.UUID
    model: str


class VoiceMessageIn(BaseModel):
    role: Literal["user", "assistant", "tool"]
    content: str = Field(default="", max_length=200_000)
    # assistant: [{"id", "name", "args"}]
    tool_calls: list[dict[str, Any]] | None = None
    # tool: the id of the call this result answers
    tool_call_id: str | None = None
    model_used: str | None = None


class VoiceMessagesRequest(BaseModel):
    user_id: uuid.UUID
    conversation_id: uuid.UUID
    messages: list[VoiceMessageIn] = Field(max_length=50)


class VoiceHistoryMessage(BaseModel):
    role: str
    content: str


class VoiceHistoryResponse(BaseModel):
    title: str | None
    messages: list[VoiceHistoryMessage]
