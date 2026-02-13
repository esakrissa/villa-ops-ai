"""Tests for chat conversation CRUD API endpoints (list, get, delete).

NOTE: The SSE streaming endpoint (POST /api/v1/chat) is not tested here
as it requires a running LLM + MCP server. Only the conversation management
endpoints are covered.
"""

import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.memory import create_conversation, save_messages
from app.models.user import User
from langchain_core.messages import HumanMessage, AIMessage


class TestListConversations:
    """Test GET /api/v1/chat/conversations."""

    async def test_list_empty(self, client: AsyncClient, auth_headers: dict):
        response = await client.get("/api/v1/chat/conversations", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    async def test_list_with_conversations(
        self,
        client: AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession,
        test_user: User,
    ):
        await create_conversation(db_session, test_user.id, title="Chat 1")
        await create_conversation(db_session, test_user.id, title="Chat 2")
        await db_session.flush()

        response = await client.get("/api/v1/chat/conversations", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 2
        # Each conversation should have expected fields
        conv = data[0]
        assert "id" in conv
        assert "title" in conv
        assert "created_at" in conv
        assert "message_count" in conv

    async def test_list_requires_auth(self, client: AsyncClient):
        response = await client.get("/api/v1/chat/conversations")
        assert response.status_code in (401, 403)

    async def test_list_with_pagination(
        self,
        client: AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession,
        test_user: User,
    ):
        for i in range(5):
            await create_conversation(db_session, test_user.id, title=f"Conv {i}")
        await db_session.flush()

        response = await client.get(
            "/api/v1/chat/conversations?limit=2&offset=0", headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2


class TestGetConversation:
    """Test GET /api/v1/chat/conversations/{id}."""

    async def test_get_existing(
        self,
        client: AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession,
        test_user: User,
    ):
        conv = await create_conversation(db_session, test_user.id, title="Detail Test")
        conv_id = conv.id
        await save_messages(db_session, conv_id, [HumanMessage(content="Hello")])
        await db_session.flush()
        # Remove cached objects so the API re-queries with fresh selectin load
        db_session.expunge_all()

        response = await client.get(
            f"/api/v1/chat/conversations/{conv_id}", headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(conv_id)
        assert data["title"] == "Detail Test"
        assert "messages" in data
        assert len(data["messages"]) >= 1
        assert data["messages"][0]["role"] == "user"
        assert data["messages"][0]["content"] == "Hello"

    async def test_get_not_found(self, client: AsyncClient, auth_headers: dict):
        fake_id = uuid.uuid4()
        response = await client.get(
            f"/api/v1/chat/conversations/{fake_id}", headers=auth_headers
        )
        assert response.status_code == 404

    async def test_get_requires_auth(self, client: AsyncClient):
        fake_id = uuid.uuid4()
        response = await client.get(f"/api/v1/chat/conversations/{fake_id}")
        assert response.status_code in (401, 403)


class TestDeleteConversation:
    """Test DELETE /api/v1/chat/conversations/{id}."""

    async def test_delete_existing(
        self,
        client: AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession,
        test_user: User,
    ):
        conv = await create_conversation(db_session, test_user.id, title="To Delete")
        await db_session.flush()

        response = await client.delete(
            f"/api/v1/chat/conversations/{conv.id}", headers=auth_headers
        )
        assert response.status_code == 204

        # Verify it's gone
        response = await client.get(
            f"/api/v1/chat/conversations/{conv.id}", headers=auth_headers
        )
        assert response.status_code == 404

    async def test_delete_not_found(self, client: AsyncClient, auth_headers: dict):
        fake_id = uuid.uuid4()
        response = await client.delete(
            f"/api/v1/chat/conversations/{fake_id}", headers=auth_headers
        )
        assert response.status_code == 404

    async def test_delete_requires_auth(self, client: AsyncClient):
        fake_id = uuid.uuid4()
        response = await client.delete(f"/api/v1/chat/conversations/{fake_id}")
        assert response.status_code in (401, 403)
