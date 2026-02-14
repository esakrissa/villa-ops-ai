"""Chat API router with SSE streaming and conversation CRUD.

POST /api/v1/chat         — Send a message, stream agent response via SSE
GET  /api/v1/chat/conversations       — List user's conversations
GET  /api/v1/chat/conversations/{id}  — Get conversation with full history
DELETE /api/v1/chat/conversations/{id} — Delete a conversation
"""

import json
import logging
import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, ToolMessage
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
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


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
        """SSE event generator — uses its own DB session.

        Uses mixed stream_mode=["messages", "updates"]:
        - "messages" streams LLM tokens as (AIMessageChunk, metadata) tuples
        - "updates" emits node state changes {node_name: {key: value}}
          after each node completes — gives us complete AIMessages with
          tool_calls and ToolMessages in real-time for persistence
        """
        async with async_session_factory() as session:
            try:
                # Load existing messages from DB (if continuing conversation)
                history = await load_conversation_messages(session, conversation_id, user_id)

                # Append new user message
                user_msg = HumanMessage(content=message_text)
                history.append(user_msg)

                # Create agent graph
                agent = await create_agent()

                # Collect new messages from "updates" mode for persistence
                new_messages: list = [user_msg]

                async for mode, chunk in agent.astream(
                    {"messages": history},
                    stream_mode=["messages", "updates"],
                ):
                    if await request.is_disconnected():
                        logger.info("Client disconnected, stopping stream")
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
                        # "updates" emits {node_name: {key: value}} after each node.
                        # Collect complete messages for persistence and stream
                        # tool results and final AI text to the client.
                        for _node_name, node_output in chunk.items():
                            node_msgs = node_output.get("messages", [])
                            for msg in node_msgs:
                                new_messages.append(msg)
                                if isinstance(msg, ToolMessage):
                                    yield json.dumps({
                                        "type": "tool_result",
                                        "name": getattr(msg, "name", ""),
                                        "result": msg.content if isinstance(msg.content, str) else str(msg.content),
                                    })
                                elif isinstance(msg, AIMessage) and msg.tool_calls:
                                    # Emit tool_call events — "messages" mode may
                                    # not emit AIMessageChunks with tool_calls for
                                    # some models (e.g. Gemini via LiteLLM).
                                    for tc in msg.tool_calls:
                                        yield json.dumps({
                                            "type": "tool_call",
                                            "name": tc.get("name", ""),
                                            "args": tc.get("args", {}),
                                        })
                                elif isinstance(msg, AIMessage) and msg.content and not msg.tool_calls:
                                    # Final AI text response — "messages" mode may
                                    # not emit token chunks for all models, so emit
                                    # the complete text from "updates" as a fallback.
                                    content = msg.content if isinstance(msg.content, str) else str(msg.content)
                                    yield json.dumps({
                                        "type": "token",
                                        "content": content,
                                    })

                # Save all new messages to DB
                if new_messages:
                    await save_messages(session, conversation_id, new_messages, model_used=model_name)
                    await session.commit()

                # Record LLM usage for billing/plan gating
                usage_record = LLMUsage(
                    user_id=user_id,
                    model=model_name,
                    provider=model_name.split("/")[0],
                    input_tokens=0,
                    output_tokens=0,
                    cost=Decimal("0"),
                    latency_ms=0,
                    cached=False,
                )
                session.add(usage_record)
                await session.commit()

                # Send completion event
                yield json.dumps({
                    "type": "done",
                    "conversation_id": str(conversation_id),
                })

            except Exception:
                logger.exception("Error during chat streaming")
                yield json.dumps({
                    "type": "error",
                    "message": "An error occurred while processing your request.",
                })

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
