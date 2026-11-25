"""Tests for voice mode (Villa): LiveKit token endpoint and the agent's transcript endpoints."""

import json
import uuid

import pytest
from httpx import AsyncClient
from jose import jwt
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1 import voice as voice_api
from app.config import settings
from app.models.conversation import Conversation, Message
from app.models.llm_usage import LLMUsage
from app.models.user import User
from app.voice.livekit_token import mint_voice_token

SECRET = "test-voice-agent-secret"
LK_SECRET = "lk-test-secret-0123456789abcdef0123456789"


@pytest.fixture
def voice_on(monkeypatch):
    monkeypatch.setattr(settings, "livekit_url", "wss://example.livekit.cloud")
    monkeypatch.setattr(settings, "livekit_api_key", "APItest")
    monkeypatch.setattr(settings, "livekit_api_secret", LK_SECRET)
    monkeypatch.setattr(settings, "openrouter_api_key", "sk-or-test")
    monkeypatch.setattr(settings, "voice_agent_secret", SECRET)

    async def no_llm_title(_message: str) -> None:
        return None

    monkeypatch.setattr(voice_api, "generate_llm_title", no_llm_title)


def agent_headers() -> dict[str, str]:
    return {"X-Voice-Agent-Key": SECRET}


# ---- token -----------------------------------------------------------------------------


def test_token_claims_dispatch_the_agent_with_metadata():
    user_id = uuid.uuid4()
    grant = mint_voice_token(
        api_key="APItest",
        api_secret=LK_SECRET,
        agent_name="villa",
        user_id=user_id,
        user_name="Esa",
        metadata={"user_id": str(user_id), "conversation_id": "c1"},
        now=1_800_000_000,
    )
    claims = jwt.decode(grant.token, LK_SECRET, algorithms=["HS256"], options={"verify_exp": False, "verify_nbf": False})
    assert claims["iss"] == "APItest"
    assert claims["sub"] == grant.identity
    assert claims["exp"] - claims["nbf"] == 15 * 60
    assert claims["video"] == {
        "roomJoin": True,
        "room": grant.room_name,
        "canPublish": True,
        "canSubscribe": True,
        "canPublishData": True,
    }
    agents = claims["roomConfig"]["agents"]
    assert agents[0]["agentName"] == "villa"
    assert json.loads(agents[0]["metadata"])["user_id"] == str(user_id)
    assert grant.room_name.startswith("villa-")


# ---- config / session ------------------------------------------------------------------


class TestVoiceSession:
    async def test_config_reports_off_without_keys(self, client: AsyncClient, auth_headers: dict, monkeypatch):
        monkeypatch.setattr(settings, "livekit_api_key", "")
        r = await client.get("/api/v1/voice/config", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["enabled"] is False

    async def test_config_lists_models(self, client: AsyncClient, auth_headers: dict, voice_on):
        r = await client.get("/api/v1/voice/config", headers=auth_headers)
        data = r.json()
        assert data["enabled"] is True
        assert data["models"][0]["default"] is True
        assert data["models"][0]["id"] == settings.voice_models[0]

    async def test_session_requires_auth(self, client: AsyncClient, voice_on):
        r = await client.post("/api/v1/voice/session", json={})
        assert r.status_code in (401, 403)

    async def test_session_503_when_not_configured(self, client: AsyncClient, auth_headers: dict, monkeypatch):
        monkeypatch.setattr(settings, "livekit_url", "")
        r = await client.post("/api/v1/voice/session", json={}, headers=auth_headers)
        assert r.status_code == 503

    async def test_new_session_signs_user_and_model(
        self, client: AsyncClient, auth_headers: dict, test_user: User, voice_on
    ):
        r = await client.post(
            "/api/v1/voice/session",
            json={"model": "openai/gpt-6-sol", "disabled_tools": ["send_notification"]},
            headers=auth_headers,
        )
        assert r.status_code == 201, r.text
        data = r.json()
        assert data["server_url"] == "wss://example.livekit.cloud"
        assert data["model"] == "openai/gpt-6-sol"
        claims = jwt.decode(data["participant_token"], LK_SECRET, algorithms=["HS256"])
        meta = json.loads(claims["roomConfig"]["agents"][0]["metadata"])
        assert meta["user_id"] == str(test_user.id)
        assert meta["conversation_id"] == data["conversation_id"]
        assert meta["disabled_tools"] == ["send_notification"]

    async def test_unknown_model_falls_back_to_default(self, client: AsyncClient, auth_headers: dict, voice_on):
        r = await client.post("/api/v1/voice/session", json={"model": "evil/model"}, headers=auth_headers)
        assert r.json()["model"] == settings.voice_models[0]

    async def test_cannot_continue_someone_elses_conversation(
        self, client: AsyncClient, auth_headers: dict, db_session: AsyncSession, test_free_user: User, voice_on
    ):
        other = Conversation(user_id=test_free_user.id, title="theirs")
        db_session.add(other)
        await db_session.flush()
        r = await client.post("/api/v1/voice/session", json={"conversation_id": str(other.id)}, headers=auth_headers)
        assert r.status_code == 404


# ---- internal transcript endpoints -----------------------------------------------------


class TestVoiceTranscript:
    async def test_rejects_missing_or_wrong_secret(self, client: AsyncClient, test_user: User, voice_on):
        body = {"user_id": str(test_user.id), "conversation_id": str(uuid.uuid4()), "messages": []}
        r = await client.post("/api/v1/voice/internal/messages", json=body)
        assert r.status_code == 401
        r = await client.post("/api/v1/voice/internal/messages", json=body, headers={"X-Voice-Agent-Key": "nope"})
        assert r.status_code == 401

    async def test_rejected_when_secret_unset(self, client: AsyncClient, test_user: User, monkeypatch):
        monkeypatch.setattr(settings, "voice_agent_secret", "")
        body = {"user_id": str(test_user.id), "conversation_id": str(uuid.uuid4()), "messages": []}
        r = await client.post("/api/v1/voice/internal/messages", json=body, headers={"X-Voice-Agent-Key": ""})
        assert r.status_code == 401

    async def test_saves_turns_creates_conversation_and_counts_usage(
        self, client: AsyncClient, db_session: AsyncSession, test_user: User, voice_on
    ):
        conv_id = uuid.uuid4()
        body = {
            "user_id": str(test_user.id),
            "conversation_id": str(conv_id),
            "messages": [
                {"role": "assistant", "content": "Hi, I'm Villa."},
                {"role": "user", "content": "Plan a week in Ubud", "model_used": "anthropic/claude-haiku-5.5"},
                {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [{"id": "call_1", "name": "show_itinerary", "args": {"title": "Ubud"}}],
                },
                {"role": "tool", "content": '{"kind": "itinerary"}', "tool_call_id": "call_1"},
            ],
        }
        r = await client.post("/api/v1/voice/internal/messages", json=body, headers=agent_headers())
        assert r.status_code == 204, r.text

        conv = await db_session.get(Conversation, conv_id)
        assert conv is not None and conv.user_id == test_user.id
        assert conv.title == "Plan a week in Ubud"
        rows = (
            await db_session.execute(
                select(Message.role, Message.tool_results)
                .where(Message.conversation_id == conv_id)
                .order_by(Message.created_at)
            )
        ).all()
        assert [r.role for r in rows] == ["assistant", "user", "assistant", "tool"]
        assert rows[3].tool_results == {"tool_call_id": "call_1"}
        usage = await db_session.scalar(
            select(func.count()).select_from(LLMUsage).where(LLMUsage.user_id == test_user.id)
        )
        assert usage == 1  # one spoken question = one AI query

    async def test_cannot_write_into_another_users_conversation(
        self, client: AsyncClient, db_session: AsyncSession, test_user: User, test_free_user: User, voice_on
    ):
        theirs = Conversation(user_id=test_free_user.id, title="theirs")
        db_session.add(theirs)
        await db_session.flush()
        body = {
            "user_id": str(test_user.id),
            "conversation_id": str(theirs.id),
            "messages": [{"role": "user", "content": "hi"}],
        }
        r = await client.post("/api/v1/voice/internal/messages", json=body, headers=agent_headers())
        assert r.status_code == 404

    async def test_history_returns_recent_text_turns(
        self, client: AsyncClient, db_session: AsyncSession, test_user: User, voice_on
    ):
        conv_id = uuid.uuid4()
        body = {
            "user_id": str(test_user.id),
            "conversation_id": str(conv_id),
            "messages": [
                {"role": "user", "content": "Who checks in today?"},
                {"role": "assistant", "content": "", "tool_calls": [{"id": "c", "name": "booking_search", "args": {}}]},
                {"role": "tool", "content": "{}", "tool_call_id": "c"},
                {"role": "assistant", "content": "Two guests check in today."},
            ],
        }
        await client.post("/api/v1/voice/internal/messages", json=body, headers=agent_headers())
        r = await client.get(
            f"/api/v1/voice/internal/conversations/{conv_id}",
            params={"user_id": str(test_user.id)},
            headers=agent_headers(),
        )
        assert r.status_code == 200
        assert [m["role"] for m in r.json()["messages"]] == ["user", "assistant"]

    async def test_history_of_new_conversation_is_empty(self, client: AsyncClient, test_user: User, voice_on):
        r = await client.get(
            f"/api/v1/voice/internal/conversations/{uuid.uuid4()}",
            params={"user_id": str(test_user.id)},
            headers=agent_headers(),
        )
        assert r.status_code == 200
        assert r.json() == {"title": None, "messages": []}
