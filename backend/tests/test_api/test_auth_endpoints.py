"""Tests for auth API endpoints: register, login, refresh, me."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import create_token_pair, create_refresh_token, create_access_token
from app.auth.passwords import hash_password
from app.models.user import User


class TestRegister:
    """POST /api/v1/auth/register."""

    async def test_register_success(self, client: AsyncClient):
        unique = uuid.uuid4().hex[:8]
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": f"register-{unique}@test.com",
                "password": "securepass123",
                "name": "New User",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["user"]["email"] == f"register-{unique}@test.com"
        assert "tokens" in data
        assert "access_token" in data["tokens"]
        assert "refresh_token" in data["tokens"]

    async def test_register_duplicate_email(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        unique = uuid.uuid4().hex[:8]
        email = f"dup-{unique}@test.com"

        user = User(
            email=email,
            hashed_password=hash_password("testpass"),
            name="Existing",
            auth_provider="local",
            is_active=True,
        )
        db_session.add(user)
        await db_session.flush()

        response = await client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "newpass123", "name": "New"},
        )
        assert response.status_code == 409
        assert "already registered" in response.json()["detail"].lower()

    async def test_register_missing_fields(self, client: AsyncClient):
        response = await client.post(
            "/api/v1/auth/register",
            json={"email": "bad@test.com"},
        )
        assert response.status_code == 422


class TestLogin:
    """POST /api/v1/auth/login."""

    async def test_login_success(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        unique = uuid.uuid4().hex[:8]
        email = f"login-{unique}@test.com"
        password = "correct_pass"

        user = User(
            email=email,
            hashed_password=hash_password(password),
            name="Login User",
            auth_provider="local",
            is_active=True,
        )
        db_session.add(user)
        await db_session.flush()

        response = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["user"]["email"] == email
        assert "access_token" in data["tokens"]

    async def test_login_wrong_password(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        unique = uuid.uuid4().hex[:8]
        email = f"wrongpw-{unique}@test.com"

        user = User(
            email=email,
            hashed_password=hash_password("right_pass"),
            name="Wrong PW",
            auth_provider="local",
            is_active=True,
        )
        db_session.add(user)
        await db_session.flush()

        response = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "wrong_pass"},
        )
        assert response.status_code == 401

    async def test_login_nonexistent_user(self, client: AsyncClient):
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@test.com", "password": "whatever"},
        )
        assert response.status_code == 401

    async def test_login_inactive_user(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        unique = uuid.uuid4().hex[:8]
        email = f"inactive-{unique}@test.com"

        user = User(
            email=email,
            hashed_password=hash_password("somepass"),
            name="Inactive",
            auth_provider="local",
            is_active=False,
        )
        db_session.add(user)
        await db_session.flush()

        response = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "somepass"},
        )
        assert response.status_code == 403


class TestRefresh:
    """POST /api/v1/auth/refresh."""

    async def test_refresh_success(self, client: AsyncClient, test_user: User):
        tokens = create_token_pair(str(test_user.id))
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": tokens["refresh_token"]},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data

    async def test_refresh_with_access_token_fails(
        self, client: AsyncClient, test_user: User
    ):
        tokens = create_token_pair(str(test_user.id))
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": tokens["access_token"]},
        )
        assert response.status_code == 401

    async def test_refresh_with_invalid_token(self, client: AsyncClient):
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "garbage.token.value"},
        )
        assert response.status_code == 401

    async def test_refresh_with_nonexistent_user(self, client: AsyncClient):
        fake_id = str(uuid.uuid4())
        token = create_refresh_token({"sub": fake_id})
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": token},
        )
        assert response.status_code == 401


class TestMe:
    """GET /api/v1/auth/me."""

    async def test_me_success(
        self, client: AsyncClient, auth_headers: dict, test_user: User
    ):
        response = await client.get("/api/v1/auth/me", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == test_user.email

    async def test_me_no_auth(self, client: AsyncClient):
        response = await client.get("/api/v1/auth/me")
        assert response.status_code in (401, 403)

    async def test_me_with_refresh_token_fails(
        self, client: AsyncClient, test_user: User
    ):
        tokens = create_token_pair(str(test_user.id))
        headers = {"Authorization": f"Bearer {tokens['refresh_token']}"}
        response = await client.get("/api/v1/auth/me", headers=headers)
        assert response.status_code == 401
