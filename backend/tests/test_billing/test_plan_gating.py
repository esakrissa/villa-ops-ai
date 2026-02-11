"""Tests for plan gating dependencies — property limits, AI query limits, notifications."""

import uuid
from datetime import datetime

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import create_token_pair
from app.auth.passwords import hash_password
from app.billing.dependencies import (
    check_ai_query_limit,
    check_notification_access,
    check_property_limit,
)
from app.models.llm_usage import LLMUsage
from app.models.property import Property
from app.models.subscription import Subscription
from app.models.user import User


async def _create_user_with_plan(
    db_session: AsyncSession, plan: str
) -> tuple[User, dict[str, str]]:
    """Create a user with a specific plan and return (user, auth_headers)."""
    unique = uuid.uuid4().hex[:8]
    user = User(
        email=f"user-{unique}@test.com",
        hashed_password=hash_password("testpass"),
        name="Test User",
        auth_provider="local",
        is_active=True,
        role="manager",
    )
    db_session.add(user)
    await db_session.flush()

    subscription = Subscription(user_id=user.id, plan=plan, status="active")
    db_session.add(subscription)
    await db_session.flush()

    tokens = create_token_pair(str(user.id))
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    return user, headers


async def _add_properties(db_session: AsyncSession, user: User, count: int) -> None:
    """Insert properties directly in DB (bypasses API plan gating)."""
    for i in range(count):
        prop = Property(
            owner_id=user.id,
            name=f"Villa {i}",
            property_type="villa",
        )
        db_session.add(prop)
    await db_session.flush()


async def _add_llm_usage(
    db_session: AsyncSession,
    user: User,
    count: int,
    created_at: datetime | None = None,
) -> None:
    """Insert LLM usage rows directly in DB."""
    for _ in range(count):
        usage = LLMUsage(user_id=user.id, model="test", provider="test")
        db_session.add(usage)
    await db_session.flush()

    if created_at is not None:
        # Update the created_at for the last `count` rows
        from sqlalchemy import select, update

        result = await db_session.execute(
            select(LLMUsage.id).where(LLMUsage.user_id == user.id)
        )
        ids = [row[0] for row in result.all()]
        for uid in ids:
            await db_session.execute(
                update(LLMUsage)
                .where(LLMUsage.id == uid)
                .values(created_at=created_at)
            )
        await db_session.flush()


# ---------------------------------------------------------------------------
# Property limit tests
# ---------------------------------------------------------------------------


class TestPropertyLimit:
    """Test check_property_limit dependency."""

    @pytest.mark.asyncio
    async def test_free_user_can_create_first_property(
        self, db_session: AsyncSession, client
    ):
        """Free user with 0 properties can create one."""
        _, headers = await _create_user_with_plan(db_session, "free")
        response = await client.post(
            "/api/v1/properties",
            json={
                "name": "My Villa",
                "property_type": "villa",
                "location": "Ubud, Bali",
                "max_guests": 4,
                "base_price_per_night": 100.00,
            },
            headers=headers,
        )
        assert response.status_code == 201

    @pytest.mark.asyncio
    async def test_free_user_blocked_at_limit(
        self, db_session: AsyncSession, client
    ):
        """Free user with 1 property is blocked from creating another."""
        user, headers = await _create_user_with_plan(db_session, "free")
        await _add_properties(db_session, user, 1)

        response = await client.post(
            "/api/v1/properties",
            json={
                "name": "Another Villa",
                "property_type": "villa",
                "location": "Seminyak, Bali",
                "max_guests": 4,
                "base_price_per_night": 100.00,
            },
            headers=headers,
        )
        assert response.status_code == 402

    @pytest.mark.asyncio
    async def test_free_user_402_detail_structure(
        self, db_session: AsyncSession, client
    ):
        """402 response has proper structured detail."""
        user, headers = await _create_user_with_plan(db_session, "free")
        await _add_properties(db_session, user, 1)

        response = await client.post(
            "/api/v1/properties",
            json={
                "name": "Another Villa",
                "property_type": "villa",
                "location": "Seminyak, Bali",
                "max_guests": 4,
                "base_price_per_night": 100.00,
            },
            headers=headers,
        )
        assert response.status_code == 402
        detail = response.json()["detail"]
        assert "message" in detail
        assert detail["limit"] == 1
        assert detail["current"] == 1
        assert detail["plan"] == "free"
        assert detail["upgrade_url"] == "/api/v1/billing/checkout"

    @pytest.mark.asyncio
    async def test_pro_user_can_create_up_to_5(
        self, db_session: AsyncSession, client
    ):
        """Pro user with 4 properties can still create one more."""
        user, headers = await _create_user_with_plan(db_session, "pro")
        await _add_properties(db_session, user, 4)

        response = await client.post(
            "/api/v1/properties",
            json={
                "name": "Villa Five",
                "property_type": "villa",
                "location": "Canggu, Bali",
                "max_guests": 4,
                "base_price_per_night": 100.00,
            },
            headers=headers,
        )
        assert response.status_code == 201

    @pytest.mark.asyncio
    async def test_pro_user_blocked_at_5(
        self, db_session: AsyncSession, client
    ):
        """Pro user with 5 properties is blocked."""
        user, headers = await _create_user_with_plan(db_session, "pro")
        await _add_properties(db_session, user, 5)

        response = await client.post(
            "/api/v1/properties",
            json={
                "name": "Villa Six",
                "property_type": "villa",
                "location": "Canggu, Bali",
                "max_guests": 4,
                "base_price_per_night": 100.00,
            },
            headers=headers,
        )
        assert response.status_code == 402

    @pytest.mark.asyncio
    async def test_business_user_unlimited(
        self, db_session: AsyncSession, client
    ):
        """Business user can create properties without limit."""
        user, headers = await _create_user_with_plan(db_session, "business")
        await _add_properties(db_session, user, 10)

        response = await client.post(
            "/api/v1/properties",
            json={
                "name": "Villa Eleven",
                "property_type": "villa",
                "location": "Canggu, Bali",
                "max_guests": 4,
                "base_price_per_night": 100.00,
            },
            headers=headers,
        )
        assert response.status_code == 201


# ---------------------------------------------------------------------------
# AI query limit tests
# ---------------------------------------------------------------------------


class TestAiQueryLimit:
    """Test check_ai_query_limit dependency directly."""

    @pytest.mark.asyncio
    async def test_free_user_under_limit(self, db_session: AsyncSession):
        """Free user with 49 queries should pass."""
        user, _ = await _create_user_with_plan(db_session, "free")
        await _add_llm_usage(db_session, user, 49)
        # Should NOT raise
        await check_ai_query_limit(db=db_session, user=user)

    @pytest.mark.asyncio
    async def test_free_user_at_limit(self, db_session: AsyncSession):
        """Free user with 50 queries should be blocked."""
        user, _ = await _create_user_with_plan(db_session, "free")
        await _add_llm_usage(db_session, user, 50)

        with pytest.raises(HTTPException) as exc_info:
            await check_ai_query_limit(db=db_session, user=user)
        assert exc_info.value.status_code == 402
        assert exc_info.value.detail["limit"] == 50
        assert exc_info.value.detail["current"] == 50

    @pytest.mark.asyncio
    async def test_business_user_unlimited(self, db_session: AsyncSession):
        """Business user should never be blocked."""
        user, _ = await _create_user_with_plan(db_session, "business")
        await _add_llm_usage(db_session, user, 100)
        # Should NOT raise
        await check_ai_query_limit(db=db_session, user=user)

    @pytest.mark.asyncio
    async def test_counts_only_current_period(self, db_session: AsyncSession):
        """Only queries in the current billing period should count."""
        user, _ = await _create_user_with_plan(db_session, "free")

        # Add 49 queries in current month (these count)
        await _add_llm_usage(db_session, user, 49)

        # Add 1 query from last month (should NOT count)
        old_usage = LLMUsage(user_id=user.id, model="test", provider="test")
        db_session.add(old_usage)
        await db_session.flush()
        old_usage.created_at = datetime(2025, 1, 1)
        await db_session.flush()

        # Total is 50, but only 49 in current period — should pass
        await check_ai_query_limit(db=db_session, user=user)

    @pytest.mark.asyncio
    async def test_pro_user_higher_limit(self, db_session: AsyncSession):
        """Pro user has 500 query limit."""
        user, _ = await _create_user_with_plan(db_session, "pro")
        await _add_llm_usage(db_session, user, 50)
        # Should NOT raise — well under 500 limit
        await check_ai_query_limit(db=db_session, user=user)


# ---------------------------------------------------------------------------
# Notification access tests
# ---------------------------------------------------------------------------


class TestNotificationAccess:
    """Test check_notification_access dependency directly."""

    @pytest.mark.asyncio
    async def test_free_user_blocked(self, db_session: AsyncSession):
        """Free users should not have notification access."""
        user, _ = await _create_user_with_plan(db_session, "free")
        with pytest.raises(HTTPException) as exc_info:
            await check_notification_access(db=db_session, user=user)
        assert exc_info.value.status_code == 402
        assert "Notifications require" in exc_info.value.detail["message"]

    @pytest.mark.asyncio
    async def test_pro_user_allowed(self, db_session: AsyncSession):
        """Pro users should have notification access."""
        user, _ = await _create_user_with_plan(db_session, "pro")
        # Should NOT raise
        await check_notification_access(db=db_session, user=user)

    @pytest.mark.asyncio
    async def test_business_user_allowed(self, db_session: AsyncSession):
        """Business users should have notification access."""
        user, _ = await _create_user_with_plan(db_session, "business")
        # Should NOT raise
        await check_notification_access(db=db_session, user=user)
