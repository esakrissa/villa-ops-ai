"""Shared test configuration and fixtures.

Uses a transactional rollback strategy per test for full isolation:
- Each test gets its own nested transaction that rolls back after the test.
- The test database `villa_ops_test` must exist before running tests.
"""

import uuid
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.auth.jwt import create_token_pair
from app.auth.passwords import hash_password
from app.config import settings
from app.database import Base, get_db
from app.main import app
from app.models.subscription import Subscription
from app.models.user import User

# ---------------------------------------------------------------------------
# Test database engine — uses the same PG instance but `villa_ops_test` DB.
# Replace the last path segment of the configured URL with the test DB name.
# ---------------------------------------------------------------------------

_base_url = settings.async_database_url
# Handle both `villa_ops` and any other db name in the URL
_test_db_url = _base_url.rsplit("/", 1)[0] + "/villa_ops_test"


def _make_engine():
    return create_async_engine(
        _test_db_url,
        echo=False,
        pool_pre_ping=True,
    )


# ---------------------------------------------------------------------------
# Session-scoped: create / drop all tables once per test session
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def test_engine():
    """Create a session-scoped engine tied to the session event loop."""
    engine = _make_engine()
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def setup_test_db(test_engine):
    """Create all tables at the start of the session and drop them at the end."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


# ---------------------------------------------------------------------------
# Per-test: transactional rollback for isolation
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def db_session(test_engine, setup_test_db) -> AsyncGenerator[AsyncSession, None]:
    """Yield an async session wrapped in a transaction that always rolls back."""
    async with test_engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(bind=connection, expire_on_commit=False)

        try:
            yield session
        finally:
            await session.close()
            await transaction.rollback()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Provide an httpx AsyncClient wired to use the test DB session."""

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Convenience fixtures: authenticated user
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create and return a test user directly in the DB."""
    unique = uuid.uuid4().hex[:8]
    user = User(
        email=f"testuser-{unique}@test.com",
        hashed_password=hash_password("testpass123"),
        name="Test User",
        auth_provider="local",
        is_active=True,
        role="manager",
    )
    db_session.add(user)
    await db_session.flush()

    subscription = Subscription(user_id=user.id, plan="business", status="active")
    db_session.add(subscription)
    await db_session.flush()
    await db_session.refresh(user)

    return user


@pytest_asyncio.fixture
async def auth_headers(test_user: User) -> dict[str, str]:
    """Return Authorization headers for the test user."""
    tokens = create_token_pair(str(test_user.id))
    return {"Authorization": f"Bearer {tokens['access_token']}"}


@pytest_asyncio.fixture
async def test_free_user(db_session: AsyncSession) -> User:
    """Create and return a free-plan test user."""
    unique = uuid.uuid4().hex[:8]
    user = User(
        email=f"freeuser-{unique}@test.com",
        hashed_password=hash_password("testpass123"),
        name="Free User",
        auth_provider="local",
        is_active=True,
        role="manager",
    )
    db_session.add(user)
    await db_session.flush()

    subscription = Subscription(user_id=user.id, plan="free", status="active")
    db_session.add(subscription)
    await db_session.flush()
    await db_session.refresh(user)

    return user


@pytest_asyncio.fixture
async def free_auth_headers(test_free_user: User) -> dict[str, str]:
    """Return Authorization headers for the free-plan test user."""
    tokens = create_token_pair(str(test_free_user.id))
    return {"Authorization": f"Bearer {tokens['access_token']}"}


# ---------------------------------------------------------------------------
# Convenience fixtures: property, guest, booking helpers
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def test_property(client: AsyncClient, auth_headers: dict) -> dict:
    """Create and return a test property via the API."""
    response = await client.post(
        "/api/v1/properties",
        json={
            "name": "Test Villa",
            "property_type": "villa",
            "location": "Ubud, Bali",
            "max_guests": 6,
            "base_price_per_night": 150.00,
            "amenities": ["pool", "wifi", "ac"],
            "description": "A test villa for automated tests.",
        },
        headers=auth_headers,
    )
    assert response.status_code == 201, f"Failed to create test property: {response.text}"
    return response.json()


@pytest_asyncio.fixture
async def test_guest(client: AsyncClient, auth_headers: dict) -> dict:
    """Create and return a test guest via the API."""
    unique = uuid.uuid4().hex[:8]
    response = await client.post(
        "/api/v1/guests",
        json={
            "name": "Test Guest",
            "email": f"guest-{unique}@test.com",
            "phone": "+61400000000",
            "nationality": "Australian",
        },
        headers=auth_headers,
    )
    assert response.status_code == 201, f"Failed to create test guest: {response.text}"
    return response.json()
