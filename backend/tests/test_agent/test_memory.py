"""Tests for PostgreSQL-backed conversation memory (CRUD + message serialization)."""

import uuid

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from sqlalchemy.ext.asyncio import AsyncSession

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
from app.models.user import User


class TestConversationCRUD:
    """Test conversation create/read/delete operations."""

    async def test_create_conversation(self, db_session: AsyncSession, test_user: User):
        conv = await create_conversation(db_session, test_user.id, title="Test Conv")
        assert conv.id is not None
        assert conv.user_id == test_user.id
        assert conv.title == "Test Conv"

    async def test_create_conversation_no_title(self, db_session: AsyncSession, test_user: User):
        conv = await create_conversation(db_session, test_user.id)
        assert conv.id is not None
        assert conv.title is None

    async def test_list_conversations_returns_all(
        self, db_session: AsyncSession, test_user: User
    ):
        await create_conversation(db_session, test_user.id, title="First")
        await create_conversation(db_session, test_user.id, title="Second")

        convs = await get_user_conversations(db_session, test_user.id)
        assert len(convs) >= 2
        titles = {c.title for c in convs}
        assert "First" in titles
        assert "Second" in titles

    async def test_list_conversations_with_limit(
        self, db_session: AsyncSession, test_user: User
    ):
        for i in range(5):
            await create_conversation(db_session, test_user.id, title=f"Conv {i}")

        convs = await get_user_conversations(db_session, test_user.id, limit=3)
        assert len(convs) == 3

    async def test_get_conversation_message_count(
        self, db_session: AsyncSession, test_user: User
    ):
        conv = await create_conversation(db_session, test_user.id, title="Count Test")
        count = await get_conversation_message_count(db_session, conv.id)
        assert count == 0

        await save_messages(db_session, conv.id, [HumanMessage(content="Hello")])
        count = await get_conversation_message_count(db_session, conv.id)
        assert count == 1

    async def test_get_conversation_ownership_check(
        self, db_session: AsyncSession, test_user: User
    ):
        conv = await create_conversation(db_session, test_user.id, title="Owned")
        # Same user can access
        result = await get_conversation_with_messages(db_session, conv.id, test_user.id)
        assert result is not None
        assert result.id == conv.id

        # Different user cannot access
        fake_user_id = uuid.uuid4()
        result = await get_conversation_with_messages(db_session, conv.id, fake_user_id)
        assert result is None

    async def test_delete_conversation(self, db_session: AsyncSession, test_user: User):
        conv = await create_conversation(db_session, test_user.id, title="To Delete")
        deleted = await delete_conversation(db_session, conv.id, test_user.id)
        assert deleted is True

        # Verify it's gone
        result = await get_conversation_with_messages(db_session, conv.id, test_user.id)
        assert result is None

    async def test_delete_nonexistent_returns_false(
        self, db_session: AsyncSession, test_user: User
    ):
        fake_id = uuid.uuid4()
        deleted = await delete_conversation(db_session, fake_id, test_user.id)
        assert deleted is False

    async def test_delete_other_user_returns_false(
        self, db_session: AsyncSession, test_user: User
    ):
        conv = await create_conversation(db_session, test_user.id, title="Not Yours")
        fake_user_id = uuid.uuid4()
        deleted = await delete_conversation(db_session, conv.id, fake_user_id)
        assert deleted is False


class TestMessageSerialization:
    """Test saving and loading LangChain messages to/from DB."""

    async def test_save_and_load_human_message(
        self, db_session: AsyncSession, test_user: User
    ):
        conv = await create_conversation(db_session, test_user.id, title="Human Msg Test")
        conv_id = conv.id
        user_id = test_user.id
        await save_messages(db_session, conv_id, [HumanMessage(content="Hello world")])
        # Remove cached objects so next query fetches fresh from DB
        db_session.expunge_all()

        loaded = await load_conversation_messages(db_session, conv_id, user_id)
        assert len(loaded) == 1
        assert isinstance(loaded[0], HumanMessage)
        assert loaded[0].content == "Hello world"

    async def test_save_and_load_ai_message(
        self, db_session: AsyncSession, test_user: User
    ):
        conv = await create_conversation(db_session, test_user.id, title="AI Msg Test")
        conv_id = conv.id
        user_id = test_user.id
        await save_messages(
            db_session, conv_id, [AIMessage(content="I can help with that")], model_used="test-model"
        )
        db_session.expunge_all()

        loaded = await load_conversation_messages(db_session, conv_id, user_id)
        assert len(loaded) == 1
        assert isinstance(loaded[0], AIMessage)
        assert loaded[0].content == "I can help with that"

    async def test_save_and_load_ai_message_with_tool_calls(
        self, db_session: AsyncSession, test_user: User
    ):
        conv = await create_conversation(db_session, test_user.id, title="Tool Call Test")
        conv_id = conv.id
        user_id = test_user.id
        tool_calls = [{"name": "booking_search", "args": {"query": "test"}, "id": "tc_1"}]
        msg = AIMessage(content="", tool_calls=tool_calls)
        await save_messages(db_session, conv_id, [msg])
        db_session.expunge_all()

        loaded = await load_conversation_messages(db_session, conv_id, user_id)
        assert len(loaded) == 1
        assert isinstance(loaded[0], AIMessage)
        assert len(loaded[0].tool_calls) == 1
        tc = loaded[0].tool_calls[0]
        assert tc["name"] == "booking_search"
        assert tc["args"] == {"query": "test"}
        assert tc["id"] == "tc_1"

    async def test_save_and_load_tool_message(
        self, db_session: AsyncSession, test_user: User
    ):
        conv = await create_conversation(db_session, test_user.id, title="Tool Result Test")
        conv_id = conv.id
        user_id = test_user.id
        msg = ToolMessage(content='{"results": []}', tool_call_id="tc_1")
        await save_messages(db_session, conv_id, [msg])
        db_session.expunge_all()

        loaded = await load_conversation_messages(db_session, conv_id, user_id)
        assert len(loaded) == 1
        assert isinstance(loaded[0], ToolMessage)
        assert loaded[0].content == '{"results": []}'
        assert loaded[0].tool_call_id == "tc_1"

    async def test_save_multiple_messages_roundtrip(
        self, db_session: AsyncSession, test_user: User
    ):
        conv = await create_conversation(db_session, test_user.id, title="Multi Msg Test")
        conv_id = conv.id
        user_id = test_user.id
        messages = [
            HumanMessage(content="Find bookings for next week"),
            AIMessage(
                content="",
                tool_calls=[{"name": "booking_search", "args": {"query": "next week"}, "id": "tc_1"}],
            ),
            ToolMessage(content='[{"id": "b1"}]', tool_call_id="tc_1"),
            AIMessage(content="I found 1 booking for next week."),
        ]
        await save_messages(db_session, conv_id, messages)
        db_session.expunge_all()

        loaded = await load_conversation_messages(db_session, conv_id, user_id)
        assert len(loaded) == 4
        assert isinstance(loaded[0], HumanMessage)
        assert isinstance(loaded[1], AIMessage)
        assert isinstance(loaded[2], ToolMessage)
        assert isinstance(loaded[3], AIMessage)

    async def test_load_messages_wrong_user_returns_empty(
        self, db_session: AsyncSession, test_user: User
    ):
        conv = await create_conversation(db_session, test_user.id, title="Private")
        conv_id = conv.id
        await save_messages(db_session, conv_id, [HumanMessage(content="Secret")])

        fake_user_id = uuid.uuid4()
        loaded = await load_conversation_messages(db_session, conv_id, fake_user_id)
        assert loaded == []


class TestGenerateTitle:
    """Test title generation from message content."""

    def test_short_content_unchanged(self):
        assert generate_title("Hello world") == "Hello world"

    def test_long_content_truncated(self):
        long_text = "This is a very long message that should be truncated at a word boundary somewhere around here"
        title = generate_title(long_text)
        assert len(title) <= 55  # 50 + "..."
        assert title.endswith("...")

    def test_whitespace_stripped(self):
        assert generate_title("  hello  ") == "hello"

    def test_exactly_50_chars(self):
        text = "a" * 50
        assert generate_title(text) == text
