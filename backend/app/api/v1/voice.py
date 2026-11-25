"""Voice mode ("Villa") API.

GET  /api/v1/voice/config                          — is voice on, which models, which voice
POST /api/v1/voice/session                         — LiveKit token that dispatches the Villa agent
POST /api/v1/voice/internal/messages               — the agent worker saves transcript turns
GET  /api/v1/voice/internal/conversations/{id}     — the agent worker reads earlier turns

The browser talks to the agent over LiveKit (WebRTC); this API only issues the token and stores
the transcript, so a voice call becomes an ordinary conversation in the chat history. The two
internal endpoints are called by the voice agent worker with the shared ``VOICE_AGENT_SECRET``.
"""

import asyncio
import hmac
import logging
import uuid
from datetime import datetime, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.memory import generate_title
from app.agent.titles import TITLE_TIMEOUT_SECONDS, generate_llm_title
from app.api.deps import check_ai_query_limit, get_current_active_user, get_db
from app.config import settings
from app.database import async_session_factory
from app.models.conversation import Conversation, Message
from app.models.llm_usage import LLMUsage
from app.models.user import User
from app.schemas.voice import (
    VoiceConfigResponse,
    VoiceHistoryMessage,
    VoiceHistoryResponse,
    VoiceMessagesRequest,
    VoiceModel,
    VoiceSessionRequest,
    VoiceSessionResponse,
)
from app.voice.livekit_token import mint_voice_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/voice", tags=["voice"])

VOICE_NAME = "ElevenLabs Flash v2.5"
MODEL_LABELS = {
    "anthropic/claude-haiku-5.5": "Claude Haiku 5.5",
    "google/gemini-3.1-flash-lite": "Gemini 3.1 Flash-Lite",
    "openai/gpt-6-sol": "GPT-6 Sol",
    "openai/gpt-6-luna": "GPT-6 Luna",
}
# Earlier turns the agent re-reads when a call continues a chat
HISTORY_MESSAGES = 16
HISTORY_MAX_CHARS = 1200

# Background title generations (references kept so they aren't garbage-collected)
_title_tasks: set[asyncio.Task] = set()


def voice_enabled() -> bool:
    return bool(
        settings.livekit_url
        and settings.livekit_api_key
        and settings.livekit_api_secret
        and settings.openrouter_api_key
    )


def voice_models() -> list[VoiceModel]:
    return [
        VoiceModel(id=m, label=MODEL_LABELS.get(m, m.split("/")[-1]), default=i == 0)
        for i, m in enumerate(settings.voice_models)
    ]


def resolve_voice_model(requested: str | None) -> str:
    return requested if requested in settings.voice_models else settings.voice_models[0]


@router.get("/config", response_model=VoiceConfigResponse)
async def voice_config(_user: User = Depends(get_current_active_user)) -> VoiceConfigResponse:
    return VoiceConfigResponse(
        enabled=voice_enabled(),
        agent_name=settings.voice_agent_name,
        models=voice_models(),
        voice=VOICE_NAME,
    )


@router.post("/session", response_model=VoiceSessionResponse, status_code=status.HTTP_201_CREATED)
async def start_voice_session(
    body: VoiceSessionRequest,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    _limit: None = Depends(check_ai_query_limit),
) -> VoiceSessionResponse:
    """Issue a LiveKit token for a fresh room; joining it dispatches the Villa agent."""
    if not voice_enabled():
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Voice mode is not configured on this server.")

    conversation_id = body.conversation_id
    if conversation_id is not None:
        conv = await db.get(Conversation, conversation_id)
        if conv is None or conv.user_id != user.id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
    else:
        # Created lazily by the first saved turn, so a call nobody speaks in leaves no empty chat
        conversation_id = uuid.uuid4()

    model = resolve_voice_model(body.model)
    grant = mint_voice_token(
        api_key=settings.livekit_api_key,
        api_secret=settings.livekit_api_secret,
        agent_name=settings.voice_agent_name,
        user_id=user.id,
        user_name=user.name,
        metadata={
            "user_id": str(user.id),
            "user_name": user.name,
            "conversation_id": str(conversation_id),
            "model": model,
            "disabled_tools": sorted(set(body.disabled_tools)),
        },
    )
    logger.info("Voice session for user %s room=%s model=%s", user.id, grant.room_name, model)
    return VoiceSessionResponse(
        server_url=settings.livekit_url,
        participant_token=grant.token,
        room_name=grant.room_name,
        conversation_id=conversation_id,
        model=model,
    )


# ---- Internal: called by the voice agent worker -------------------------------------------


def require_agent_secret(x_voice_agent_key: str = Header(default="")) -> None:
    secret = settings.voice_agent_secret
    if not secret or not hmac.compare_digest(x_voice_agent_key.encode(), secret.encode()):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid voice agent key")


async def _get_or_create_conversation(
    db: AsyncSession, conversation_id: uuid.UUID, user_id: uuid.UUID
) -> Conversation:
    conv = await db.get(Conversation, conversation_id)
    if conv is not None:
        if conv.user_id != user_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
        return conv
    if await db.get(User, user_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    conv = Conversation(id=conversation_id, user_id=user_id, title=None)
    db.add(conv)
    await db.flush()
    return conv


async def _set_llm_title(conversation_id: uuid.UUID, first_message: str) -> None:
    try:
        title = await asyncio.wait_for(generate_llm_title(first_message), TITLE_TIMEOUT_SECONDS)
    except Exception:
        title = None
    if not title:
        return
    async with async_session_factory() as session:
        await session.execute(
            update(Conversation).where(Conversation.id == conversation_id).values(title=title)
        )
        await session.commit()


@router.post(
    "/internal/messages",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_agent_secret)],
    include_in_schema=False,
)
async def save_voice_messages(body: VoiceMessagesRequest, db: AsyncSession = Depends(get_db)) -> Response:
    """Append transcript turns to the conversation (created on the first turn)."""
    conv = await _get_or_create_conversation(db, body.conversation_id, body.user_id)

    # Explicit microsecond offsets keep the order of a batch (now() is constant per transaction)
    base_time = datetime.utcnow()
    first_user_text: str | None = None
    for i, m in enumerate(body.messages):
        row = Message(conversation_id=conv.id, role=m.role, content=m.content)
        row.created_at = base_time + timedelta(microseconds=i)
        if m.role == "assistant":
            row.model_used = m.model_used
            if m.tool_calls:
                row.tool_calls = m.tool_calls  # type: ignore[assignment]
        elif m.role == "tool":
            row.tool_results = {"tool_call_id": m.tool_call_id}  # type: ignore[assignment]
        elif m.role == "user":
            first_user_text = first_user_text or m.content
            # Each spoken question counts toward the plan's AI query limit, like a chat message
            db.add(
                LLMUsage(
                    user_id=body.user_id,
                    model=f"voice/{m.model_used or 'villa'}"[:255],
                    provider="livekit",
                    cost=Decimal("0"),
                    cached=False,
                )
            )
        db.add(row)

    needs_title = conv.title is None and first_user_text
    if needs_title:
        conv.title = generate_title(first_user_text)
    await db.commit()

    if needs_title:
        task = asyncio.create_task(_set_llm_title(conv.id, first_user_text))
        _title_tasks.add(task)
        task.add_done_callback(_title_tasks.discard)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/internal/conversations/{conversation_id}",
    response_model=VoiceHistoryResponse,
    dependencies=[Depends(require_agent_secret)],
    include_in_schema=False,
)
async def voice_history(
    conversation_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> VoiceHistoryResponse:
    """The last spoken/typed turns of a conversation, so a call can pick up where the chat was."""
    conv = await db.get(Conversation, conversation_id)
    if conv is None:
        return VoiceHistoryResponse(title=None, messages=[])
    if conv.user_id != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
    rows = (
        await db.execute(
            select(Message.role, Message.content)
            .where(
                Message.conversation_id == conversation_id,
                Message.role.in_(("user", "assistant")),
                Message.content.is_not(None),
                Message.content != "",
            )
            .order_by(Message.created_at.desc())
            .limit(HISTORY_MESSAGES)
        )
    ).all()
    messages = [
        VoiceHistoryMessage(role=role, content=content[:HISTORY_MAX_CHARS]) for role, content in reversed(rows)
    ]
    return VoiceHistoryResponse(title=conv.title, messages=messages)
