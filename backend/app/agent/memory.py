"""PostgreSQL-backed conversation memory for the LangGraph agent.

Converts between LangChain message types and the database Message model,
allowing the agent to persist and reload conversation history.
"""

import logging
import uuid
from datetime import datetime, timedelta

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, ToolMessage
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation, Message

logger = logging.getLogger(__name__)


async def create_conversation(
    db: AsyncSession,
    user_id: uuid.UUID,
    title: str | None = None,
) -> Conversation:
    """Create a new conversation for a user."""
    conversation = Conversation(user_id=user_id, title=title)
    db.add(conversation)
    await db.flush()
    await db.refresh(conversation)
    return conversation


async def get_user_conversations(
    db: AsyncSession,
    user_id: uuid.UUID,
    limit: int = 50,
    offset: int = 0,
) -> list[Conversation]:
    """List conversations for a user, newest first."""
    stmt = (
        select(Conversation)
        .where(Conversation.user_id == user_id)
        .order_by(Conversation.updated_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_conversation_message_count(
    db: AsyncSession,
    conversation_id: uuid.UUID,
) -> int:
    """Get the number of messages in a conversation."""
    stmt = select(func.count()).where(Message.conversation_id == conversation_id)
    result = await db.execute(stmt)
    return result.scalar_one()


async def get_conversation_with_messages(
    db: AsyncSession,
    conversation_id: uuid.UUID,
    user_id: uuid.UUID,
) -> Conversation | None:
    """Get a conversation with all its messages, verifying ownership."""
    stmt = select(Conversation).where(
        Conversation.id == conversation_id,
        Conversation.user_id == user_id,
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def delete_conversation(
    db: AsyncSession,
    conversation_id: uuid.UUID,
    user_id: uuid.UUID,
) -> bool:
    """Delete a conversation, verifying ownership. Returns True if deleted."""
    conversation = await get_conversation_with_messages(db, conversation_id, user_id)
    if conversation is None:
        return False
    await db.delete(conversation)
    await db.flush()
    return True


def sanitize_message_history(messages: list[AnyMessage]) -> list[AnyMessage]:
    """Remove orphaned ToolMessages that would cause Gemini API errors.

    Gemini requires every ToolMessage to have a matching tool_call (by ID)
    in the preceding AIMessage. If messages are reconstructed from DB and
    the pairing is broken, this strips the orphaned ToolMessages and any
    AIMessages that only contained tool_calls (now pointless without their
    ToolMessage responses).
    """
    # Collect all tool_call IDs from AIMessages
    valid_tool_call_ids: set[str] = set()
    for msg in messages:
        if isinstance(msg, AIMessage) and msg.tool_calls:
            for tc in msg.tool_calls:
                tc_id = tc.get("id", "")
                if tc_id:
                    valid_tool_call_ids.add(tc_id)

    # First pass: keep only ToolMessages with a matching tool_call
    sanitized: list[AnyMessage] = []
    kept_tool_call_ids: set[str] = set()
    for msg in messages:
        if isinstance(msg, ToolMessage):
            if msg.tool_call_id and msg.tool_call_id in valid_tool_call_ids:
                sanitized.append(msg)
                kept_tool_call_ids.add(msg.tool_call_id)
            else:
                logger.debug(
                    "Dropping orphaned ToolMessage with tool_call_id=%s",
                    msg.tool_call_id,
                )
        else:
            sanitized.append(msg)

    # Second pass: remove AIMessages that ONLY had tool_calls (no text content)
    # if none of their tool_calls were kept (i.e., all ToolMessages were dropped)
    final: list[AnyMessage] = []
    for msg in sanitized:
        if isinstance(msg, AIMessage) and msg.tool_calls and not msg.content:
            msg_tc_ids = {tc.get("id", "") for tc in msg.tool_calls}
            if not msg_tc_ids & kept_tool_call_ids:
                logger.debug("Dropping AIMessage with orphaned tool_calls (no content)")
                continue
        final.append(msg)

    if len(final) != len(messages):
        logger.info(
            "Sanitized message history: %d → %d messages",
            len(messages), len(final),
        )
    return final


async def load_conversation_messages(
    db: AsyncSession,
    conversation_id: uuid.UUID,
    user_id: uuid.UUID,
) -> list[AnyMessage]:
    """Load messages from a conversation and convert to LangChain message format.

    Verifies the conversation belongs to user_id before loading.
    Returns list of HumanMessage/AIMessage/ToolMessage objects.
    """
    conversation = await get_conversation_with_messages(db, conversation_id, user_id)
    if conversation is None:
        return []

    langchain_messages: list[AnyMessage] = []
    for msg in conversation.messages:
        if msg.role == "user":
            langchain_messages.append(HumanMessage(content=msg.content or ""))
        elif msg.role == "assistant":
            kwargs: dict = {"content": msg.content or ""}
            if msg.tool_calls:
                kwargs["tool_calls"] = msg.tool_calls
            langchain_messages.append(AIMessage(**kwargs))
        elif msg.role == "tool":
            tool_call_id = ""
            if msg.tool_results and isinstance(msg.tool_results, dict):
                tool_call_id = msg.tool_results.get("tool_call_id", "")
            langchain_messages.append(
                ToolMessage(
                    content=msg.content or "",
                    tool_call_id=tool_call_id,
                )
            )

    logger.debug(
        "Loaded %d messages for conversation %s", len(langchain_messages), conversation_id
    )
    return sanitize_message_history(langchain_messages)


async def save_messages(
    db: AsyncSession,
    conversation_id: uuid.UUID,
    messages: list[AnyMessage],
    model_used: str | None = None,
) -> None:
    """Save new LangChain messages to the database.

    Converts each message to a Message model instance:
    - HumanMessage -> role='user'
    - AIMessage -> role='assistant', store tool_calls if present
    - ToolMessage -> role='tool', store tool_results
    """
    # Use explicit timestamps with microsecond offsets to preserve message
    # order. PostgreSQL's now() returns the same value within a transaction,
    # so all messages in a batch would get identical created_at and load back
    # in arbitrary (UUID) order, scrambling the conversation history.
    base_time = datetime.utcnow()

    for i, msg in enumerate(messages):
        db_msg = Message(conversation_id=conversation_id)
        db_msg.created_at = base_time + timedelta(microseconds=i)

        if isinstance(msg, HumanMessage):
            db_msg.role = "user"
            db_msg.content = msg.content if isinstance(msg.content, str) else str(msg.content)
        elif isinstance(msg, AIMessage):
            db_msg.role = "assistant"
            db_msg.content = msg.content if isinstance(msg.content, str) else str(msg.content)
            db_msg.model_used = model_used
            if msg.tool_calls:
                db_msg.tool_calls = msg.tool_calls  # type: ignore[assignment]
        elif isinstance(msg, ToolMessage):
            db_msg.role = "tool"
            db_msg.content = msg.content if isinstance(msg.content, str) else str(msg.content)
            db_msg.tool_results = {"tool_call_id": msg.tool_call_id}  # type: ignore[assignment]
        else:
            continue

        db.add(db_msg)

    await db.flush()


def generate_title(content: str) -> str:
    """Generate a short title from the first user message.

    Truncates to ~50 chars at a word boundary.
    """
    content = content.strip()
    if len(content) <= 50:
        return content
    truncated = content[:50].rsplit(" ", 1)[0]
    return truncated + "..."
