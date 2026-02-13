"""Tests for auth dependencies — get_current_user edge cases."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import create_access_token, create_token_pair
from app.auth.passwords import hash_password
from app.models.subscription import Subscription
from app.models.user import User


class TestGetCurrentUser:
    """Test get_current_user dependency via the /me endpoint."""

    async def test_expired_token_rejected(self, client: AsyncClient, test_user: User):
        from datetime import timedelta

        token = create_access_token({"sub": str(test_user.id)}, expires_delta=timedelta(seconds=-1))
        headers = {"Authorization": f"Bearer {token}"}
        response = await client.get("/api/v1/auth/me", headers=headers)
        assert response.status_code == 401

    async def test_invalid_token_format(self, client: AsyncClient):
        headers = {"Authorization": "Bearer not.a.valid.jwt"}
        response = await client.get("/api/v1/auth/me", headers=headers)
        assert response.status_code == 401

    async def test_refresh_token_type_rejected(
        self, client: AsyncClient, test_user: User
    ):
        tokens = create_token_pair(str(test_user.id))
        headers = {"Authorization": f"Bearer {tokens['refresh_token']}"}
        response = await client.get("/api/v1/auth/me", headers=headers)
        assert response.status_code == 401

    async def test_nonexistent_user_id_rejected(self, client: AsyncClient):
        fake_id = str(uuid.uuid4())
        token = create_access_token({"sub": fake_id})
        headers = {"Authorization": f"Bearer {token}"}
        response = await client.get("/api/v1/auth/me", headers=headers)
        assert response.status_code == 401

    async def test_inactive_user_rejected(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        unique = uuid.uuid4().hex[:8]
        user = User(
            email=f"inactive-dep-{unique}@test.com",
            hashed_password=hash_password("testpass"),
            name="Inactive Dep",
            auth_provider="local",
            is_active=False,
        )
        db_session.add(user)
        await db_session.flush()

        # Need subscription for the user
        sub = Subscription(user_id=user.id, plan="free", status="active")
        db_session.add(sub)
        await db_session.flush()

        token = create_access_token({"sub": str(user.id)})
        headers = {"Authorization": f"Bearer {token}"}
        response = await client.get("/api/v1/auth/me", headers=headers)
        assert response.status_code == 401
