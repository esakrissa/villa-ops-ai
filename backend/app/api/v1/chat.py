"""Chat API router with SSE streaming, HITL confirmation, and conversation CRUD.

POST /api/v1/chat                            — Send a message, stream agent response via SSE
POST /api/v1/chat/{conversation_id}/resume   — Resume after HITL confirmation (approve/cancel)
GET  /api/v1/chat/conversations              — List user's conversations
GET  /api/v1/chat/conversations/{id}         — Get conversation with full history
DELETE /api/v1/chat/conversations/{id}       — Delete a conversation
"""

import json
import logging
import time
import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, ToolMessage
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.types import Command
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse
from starlette.requests import Request

from app.agent import create_agent
from app.agent.memory import (
    create_conversation,
    delete_conversation,
    generate_title,
    get_conversation_message_count,
    get_conversation_with_messages,
    get_user_conversations,
    load_conversation_messages,
    save_messages,
)
from app.api.deps import check_ai_query_limit, get_current_active_user, get_db
from app.config import settings
from app.database import async_session_factory
from app.models.llm_usage import LLMUsage
from app.models.user import User
from app.schemas.chat import (
    ChatRequest,
    ConversationDetailResponse,
    ConversationResponse,
    MessageResponse,
    ResumeRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])

# Guard against concurrent HITL resumes for the same conversation.
# Prevents double-execution if the client retries the resume request.
_active_resumes: set[uuid.UUID] = set()


async def _stream_agent(
    agent,
    agent_input,
    config: dict,
    request: Request,
    conversation_id: uuid.UUID,
    user_id: uuid.UUID,
    model_name: str,
    new_messages: list | None = None,
):
    """Shared SSE generator for both initial chat and resume flows.

    Uses mixed stream_mode=["messages", "updates"]:
    - "messages" streams LLM tokens as (AIMessageChunk, metadata) tuples
    - "updates" emits node state changes {node_name: {key: value}}
      after each node completes — gives us complete AIMessages with
      tool_calls and ToolMessages in real-time for persistence

    Detects ``__interrupt__`` events from LangGraph and emits a
    ``confirmation`` SSE event so the frontend can show a ConfirmationCard.
    """
    async with async_session_factory() as session:
        stream_ok = False
        start_time = time.monotonic()
        total_input_tokens = 0
        total_output_tokens = 0

        try:
            if new_messages is None:
                new_messages = []

            logger.info("Chat stream started [conversation=%s]", conversation_id)

            async for mode, chunk in agent.astream(
                agent_input,
                config=config,
                stream_mode=["messages", "updates"],
            ):
                if await request.is_disconnected():
                    break

                if mode == "messages":
                    msg_chunk, _metadata = chunk

                    # Stream text tokens to client
                    if isinstance(msg_chunk, AIMessageChunk) and msg_chunk.content:
                        content = msg_chunk.content if isinstance(msg_chunk.content, str) else str(msg_chunk.content)
                        yield json.dumps({
                            "type": "token",
                            "content": content,
                        })

                    # Stream tool call events to client
                    if isinstance(msg_chunk, AIMessageChunk) and msg_chunk.tool_calls:
                        for tc in msg_chunk.tool_calls:
                            yield json.dumps({
                                "type": "tool_call",
                                "name": tc.get("name", ""),
                                "args": tc.get("args", {}),
                            })

                elif mode == "updates":
                    # Check for __interrupt__ events (HITL)
                    if "__interrupt__" in chunk:
                        logger.info("HITL interrupt — awaiting user confirmation [conversation=%s]", conversation_id)
                        for intr in chunk["__interrupt__"]:
                            yield json.dumps({
                                "type": "confirmation",
                                "payload": intr.value,
                            })

                        # Save accumulated messages before pausing so they
                        # survive a page refresh (tool_call cards stay visible).
                        if new_messages:
                            await save_messages(session, conversation_id, new_messages, model_used=model_name)
                            await session.commit()

                        # Pause the stream — client must resume via /resume endpoint
                        yield json.dumps({
                            "type": "interrupted",
                            "conversation_id": str(conversation_id),
                        })
                        return

                    # "updates" emits {node_name: {key: value}} after each node.
                    # Collect complete messages for persistence and stream
                    # tool results and final AI text to the client.
                    for _node_name, node_output in chunk.items():
                        if not isinstance(node_output, dict):
                            continue
                        node_msgs = node_output.get("messages", [])
                        for msg in node_msgs:
                            new_messages.append(msg)

                            # Extract token usage from AIMessage response metadata
                            if isinstance(msg, AIMessage):
                                usage_meta = (msg.response_metadata or {}).get("token_usage") or {}
                                total_input_tokens += usage_meta.get("prompt_tokens", 0)
                                total_output_tokens += usage_meta.get("completion_tokens", 0)

                            if isinstance(msg, ToolMessage):
                                yield json.dumps({
                                    "type": "tool_result",
                                    "name": getattr(msg, "name", ""),
                                    "result": msg.content if isinstance(msg.content, str) else str(msg.content),
                                })
                            elif isinstance(msg, AIMessage) and msg.tool_calls:
                                for tc in msg.tool_calls:
                                    yield json.dumps({
                                        "type": "tool_call",
                                        "name": tc.get("name", ""),
                                        "args": tc.get("args", {}),
                                    })
                            elif isinstance(msg, AIMessage) and msg.content and not msg.tool_calls:
                                content = msg.content if isinstance(msg.content, str) else str(msg.content)
                                yield json.dumps({
                                    "type": "token",
                                    "content": content,
                                })

            stream_ok = True

        except Exception:
            logger.exception("Error during chat streaming for conversation %s", conversation_id)
            yield json.dumps({
                "type": "error",
                "message": "An error occurred while processing your request.",
            })

        finally:
            # Always persist messages and record usage, even after errors
            latency_ms = int((time.monotonic() - start_time) * 1000)

            try:
                if new_messages:
                    await save_messages(session, conversation_id, new_messages, model_used=model_name)
                    await session.commit()

                # Record LLM usage for billing/plan gating
                usage_record = LLMUsage(
                    user_id=user_id,
                    model=model_name,
                    provider=model_name.split("/")[0],
                    input_tokens=total_input_tokens,
                    output_tokens=total_output_tokens,
                    cost=Decimal("0"),
                    latency_ms=latency_ms,
                    cached=False,
                )
                session.add(usage_record)
                await session.commit()
            except Exception:
                logger.exception("Failed to persist messages/usage for conversation %s", conversation_id)

            # Always send a done event so the client exits its loading state
            yield json.dumps({
                "type": "done",
                "conversation_id": str(conversation_id),
                "ok": stream_ok,
            })


@router.post("")
async def chat(
    request: Request,
    chat_request: ChatRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_active_user),
    _limit_check: None = Depends(check_ai_query_limit),  # Plan gating
) -> EventSourceResponse:
    """Send a message and stream the agent's response via SSE."""

    # Resolve or create conversation using the request-scoped session
    conversation_id = chat_request.conversation_id
    if conversation_id:
        # Verify ownership
        conv = await get_conversation_with_messages(db, conversation_id, user.id)
        if conv is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found",
            )
    else:
        title = generate_title(chat_request.message)
        conv = await create_conversation(db, user.id, title=title)
        conversation_id = conv.id
        await db.commit()

    user_id = user.id
    message_text = chat_request.message
    model_name = settings.default_llm_model

    async def event_generator():
        db_uri = settings.psycopg_database_url
        async with AsyncPostgresSaver.from_conn_string(db_uri) as checkpointer:
            await checkpointer.setup()

            async with async_session_factory() as session:
                history = await load_conversation_messages(session, conversation_id, user_id)

            user_msg = HumanMessage(content=message_text)
            history.append(user_msg)

            agent = await create_agent(checkpointer=checkpointer)

            config = {"configurable": {"thread_id": str(conversation_id)}}
            agent_input = {"messages": history, "user_id": str(user_id)}
            new_messages: list = [user_msg]

            async for event in _stream_agent(
                agent, agent_input, config, request,
                conversation_id, user_id, model_name, new_messages,
            ):
                yield event

    return EventSourceResponse(event_generator())


@router.post("/{conversation_id}/resume")
async def resume_conversation(
    request: Request,
    conversation_id: uuid.UUID,
    body: ResumeRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_active_user),
) -> EventSourceResponse:
    """Resume a paused conversation after HITL confirmation.

    The user clicks Confirm or Cancel in the ConfirmationCard, which sends
    ``{"action": "approve"}`` or ``{"action": "cancel"}`` to this endpoint.
    LangGraph resumes the interrupted graph via ``Command(resume=...)``.
    """
    # Verify ownership
    conv = await get_conversation_with_messages(db, conversation_id, user.id)
    if conv is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    model_name = settings.default_llm_model
    logger.info("HITL resume action=%s [conversation=%s]", body.action, conversation_id)

    # Idempotency guard — prevent concurrent resumes for the same conversation
    if conversation_id in _active_resumes:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A resume is already in progress for this conversation.",
        )

    async def event_generator():
        _active_resumes.add(conversation_id)
        db_uri = settings.psycopg_database_url
        try:
            async with AsyncPostgresSaver.from_conn_string(db_uri) as checkpointer:
                await checkpointer.setup()
                agent = await create_agent(checkpointer=checkpointer)
                config = {"configurable": {"thread_id": str(conversation_id)}}

                # Resume the graph with the user's decision
                resume_input = Command(resume={"action": body.action})

                async for event in _stream_agent(
                    agent, resume_input, config, request,
                    conversation_id, user.id, model_name,
                ):
                    yield event
        except Exception:
            logger.exception("Error in resume event_generator for conversation %s", conversation_id)
            yield json.dumps({
                "type": "error",
                "message": "An error occurred while resuming the conversation.",
            })
        finally:
            _active_resumes.discard(conversation_id)

    return EventSourceResponse(event_generator())


@router.get("/conversations", response_model=list[ConversationResponse])
async def list_conversations(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_active_user),
    limit: int = 50,
    offset: int = 0,
) -> list[ConversationResponse]:
    """List the current user's conversations, newest first."""
    conversations = await get_user_conversations(db, user.id, limit=limit, offset=offset)
    results = []
    for conv in conversations:
        count = await get_conversation_message_count(db, conv.id)
        results.append(
            ConversationResponse(
                id=conv.id,
                title=conv.title,
                created_at=conv.created_at,
                updated_at=conv.updated_at,
                message_count=count,
            )
        )
    return results


@router.get("/conversations/{conversation_id}", response_model=ConversationDetailResponse)
async def get_conversation(
    conversation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_active_user),
) -> ConversationDetailResponse:
    """Get a conversation with full message history."""
    conv = await get_conversation_with_messages(db, conversation_id, user.id)
    if conv is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )
    return ConversationDetailResponse(
        id=conv.id,
        title=conv.title,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        messages=[
            MessageResponse(
                id=msg.id,
                role=msg.role,
                content=msg.content,
                tool_calls=msg.tool_calls,
                tool_results=msg.tool_results,
                model_used=msg.model_used,
                created_at=msg.created_at,
            )
            for msg in conv.messages
        ],
    )


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_conversation(
    conversation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_active_user),
) -> None:
    """Delete a conversation."""
    deleted = await delete_conversation(db, conversation_id, user.id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )
