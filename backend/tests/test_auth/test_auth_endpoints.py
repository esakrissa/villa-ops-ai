"""Tests for authentication endpoints — register, login, me, refresh."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.passwords import hash_password
from app.models.user import User

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# POST /api/v1/auth/register
# ---------------------------------------------------------------------------


class TestRegister:
    """Tests for user registration."""

    async def test_register_success(self, client: AsyncClient) -> None:
        unique = uuid.uuid4().hex[:8]
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": f"newuser-{unique}@test.com",
                "password": "securepass123",
                "name": "New User",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert "user" in data
        assert "tokens" in data
        assert data["user"]["email"] == f"newuser-{unique}@test.com"
        assert data["user"]["name"] == "New User"
        assert data["user"]["auth_provider"] == "local"
        assert data["user"]["is_active"] is True
        assert data["tokens"]["access_token"]
        assert data["tokens"]["refresh_token"]
        assert data["tokens"]["token_type"] == "bearer"

    async def test_register_duplicate_email(self, client: AsyncClient) -> None:
        unique = uuid.uuid4().hex[:8]
        email = f"dup-{unique}@test.com"
        payload = {"email": email, "password": "securepass123", "name": "First"}

        resp1 = await client.post("/api/v1/auth/register", json=payload)
        assert resp1.status_code == 201

        resp2 = await client.post("/api/v1/auth/register", json=payload)
        assert resp2.status_code == 409
        assert "already registered" in resp2.json()["detail"].lower()

    async def test_register_short_password(self, client: AsyncClient) -> None:
        unique = uuid.uuid4().hex[:8]
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": f"short-{unique}@test.com",
                "password": "short",
                "name": "Short Pass",
            },
        )
        assert response.status_code == 422

    async def test_register_invalid_email(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "not-an-email",
                "password": "securepass123",
                "name": "Bad Email",
            },
        )
        assert response.status_code == 422

    async def test_register_missing_name(self, client: AsyncClient) -> None:
        unique = uuid.uuid4().hex[:8]
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": f"noname-{unique}@test.com",
                "password": "securepass123",
            },
        )
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# POST /api/v1/auth/login
# ---------------------------------------------------------------------------


class TestLogin:
    """Tests for email/password login."""

    async def test_login_success(self, client: AsyncClient) -> None:
        unique = uuid.uuid4().hex[:8]
        email = f"login-{unique}@test.com"
        password = "securepass123"

        # Register first
        await client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": password, "name": "Login User"},
        )

        # Now login
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
        )
        assert response.status_code == 200
        data = response.json()
        assert "user" in data
        assert "tokens" in data
        assert data["user"]["email"] == email
        assert data["tokens"]["access_token"]
        assert data["tokens"]["refresh_token"]

    async def test_login_wrong_password(self, client: AsyncClient) -> None:
        unique = uuid.uuid4().hex[:8]
        email = f"wrongpw-{unique}@test.com"

        await client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "correctpass1", "name": "Wrong PW"},
        )

        response = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "wrongpassword"},
        )
        assert response.status_code == 401
        assert "invalid" in response.json()["detail"].lower()

    async def test_login_nonexistent_user(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@nowhere.com", "password": "irrelevant1"},
        )
        assert response.status_code == 401
        assert "invalid" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# GET /api/v1/auth/me
# ---------------------------------------------------------------------------


class TestMe:
    """Tests for the authenticated user profile endpoint."""

    async def test_me_authenticated(self, client: AsyncClient, auth_headers: dict, test_user: User) -> None:
        response = await client.get("/api/v1/auth/me", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == test_user.email
        assert data["name"] == test_user.name
        assert data["is_active"] is True
        assert "id" in data

    async def test_me_unauthenticated(self, client: AsyncClient) -> None:
        response = await client.get("/api/v1/auth/me")
        # FastAPI's HTTPBearer returns 401 when no credentials are provided
        assert response.status_code in (401, 403)


# ---------------------------------------------------------------------------
# POST /api/v1/auth/refresh
# ---------------------------------------------------------------------------


class TestRefresh:
    """Tests for token refresh."""

    async def test_refresh_success(self, client: AsyncClient) -> None:
        unique = uuid.uuid4().hex[:8]
        email = f"refresh-{unique}@test.com"

        # Register to get initial tokens
        reg_resp = await client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "securepass123", "name": "Refresh User"},
        )
        assert reg_resp.status_code == 201
        refresh_token = reg_resp.json()["tokens"]["refresh_token"]

        # Use the refresh token
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["access_token"]
        assert data["refresh_token"]
        assert data["token_type"] == "bearer"
        # Note: we don't assert tokens differ from originals because JWTs are
        # deterministic — if register and refresh happen within the same second
        # the iat/exp claims are identical, producing the same token.

    async def test_refresh_invalid_token(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "totally.invalid.token"},
        )
        assert response.status_code == 401
        assert "invalid" in response.json()["detail"].lower()

    async def test_refresh_with_access_token_fails(self, client: AsyncClient) -> None:
        """Using an access token (not a refresh token) should be rejected."""
        unique = uuid.uuid4().hex[:8]
        email = f"badrefresh-{unique}@test.com"

        reg_resp = await client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "securepass123", "name": "Bad Refresh"},
        )
        assert reg_resp.status_code == 201
        access_token = reg_resp.json()["tokens"]["access_token"]

        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": access_token},
        )
        assert response.status_code == 401
