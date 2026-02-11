"""Tests for subscription service — CRUD operations (pure DB, no HTTP)."""

import uuid
from datetime import datetime

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.passwords import hash_password
from app.models.subscription import Subscription
from app.models.user import User
from app.services.subscription_service import (
    downgrade_to_free,
    get_or_create_subscription,
    get_subscription_by_stripe_customer,
    get_subscription_by_stripe_subscription,
    update_subscription_from_stripe,
)


async def _create_user(db_session: AsyncSession) -> User:
    """Create a minimal test user."""
    unique = uuid.uuid4().hex[:8]
    user = User(
        email=f"svc-test-{unique}@test.com",
        hashed_password=hash_password("testpass"),
        name="Service Test User",
        auth_provider="local",
        is_active=True,
        role="manager",
    )
    db_session.add(user)
    await db_session.flush()
    return user


class TestGetOrCreateSubscription:
    """Test get_or_create_subscription."""

    @pytest.mark.asyncio
    async def test_create_free_subscription(self, db_session: AsyncSession):
        """New user gets a free subscription created automatically."""
        user = await _create_user(db_session)
        subscription = await get_or_create_subscription(db_session, user)

        assert subscription is not None
        assert subscription.user_id == user.id
        assert subscription.plan == "free"
        assert subscription.status == "active"

    @pytest.mark.asyncio
    async def test_get_existing_subscription(self, db_session: AsyncSession):
        """User with existing subscription gets it returned."""
        user = await _create_user(db_session)
        existing = Subscription(
            user_id=user.id, plan="pro", status="active",
            stripe_customer_id="cus_existing_123",
        )
        db_session.add(existing)
        await db_session.flush()

        result = await get_or_create_subscription(db_session, user)
        assert result.id == existing.id
        assert result.plan == "pro"
        assert result.stripe_customer_id == "cus_existing_123"


class TestUpdateSubscriptionFromStripe:
    """Test update_subscription_from_stripe."""

    @pytest.mark.asyncio
    async def test_update_plan_status_period(self, db_session: AsyncSession):
        """Update subscription with Stripe data."""
        user = await _create_user(db_session)
        subscription = Subscription(user_id=user.id, plan="free", status="active")
        db_session.add(subscription)
        await db_session.flush()

        period_start = datetime(2026, 2, 1)
        period_end = datetime(2026, 3, 1)

        updated = await update_subscription_from_stripe(
            db_session,
            subscription=subscription,
            stripe_subscription_id="sub_test_456",
            plan="pro",
            status="active",
            current_period_start=period_start,
            current_period_end=period_end,
            cancel_at_period_end=False,
        )

        assert updated.stripe_subscription_id == "sub_test_456"
        assert updated.plan == "pro"
        assert updated.status == "active"
        assert updated.current_period_start == period_start
        assert updated.current_period_end == period_end
        assert updated.cancel_at_period_end is False

    @pytest.mark.asyncio
    async def test_update_with_cancel_at_period_end(self, db_session: AsyncSession):
        """Update subscription with cancel_at_period_end flag."""
        user = await _create_user(db_session)
        subscription = Subscription(user_id=user.id, plan="pro", status="active")
        db_session.add(subscription)
        await db_session.flush()

        updated = await update_subscription_from_stripe(
            db_session,
            subscription=subscription,
            stripe_subscription_id="sub_test_789",
            plan="pro",
            status="active",
            cancel_at_period_end=True,
        )
        assert updated.cancel_at_period_end is True


class TestDowngradeToFree:
    """Test downgrade_to_free."""

    @pytest.mark.asyncio
    async def test_downgrade_clears_stripe_fields(self, db_session: AsyncSession):
        """Downgrade clears all Stripe-specific fields."""
        user = await _create_user(db_session)
        subscription = Subscription(
            user_id=user.id,
            plan="pro",
            status="active",
            stripe_customer_id="cus_test_123",
            stripe_subscription_id="sub_test_123",
            current_period_start=datetime(2026, 1, 1),
            current_period_end=datetime(2026, 2, 1),
            cancel_at_period_end=True,
        )
        db_session.add(subscription)
        await db_session.flush()

        downgraded = await downgrade_to_free(db_session, subscription)

        assert downgraded.plan == "free"
        assert downgraded.status == "active"
        assert downgraded.stripe_subscription_id is None
        assert downgraded.current_period_start is None
        assert downgraded.current_period_end is None
        assert downgraded.cancel_at_period_end is False
        # stripe_customer_id should be preserved (user still exists in Stripe)
        assert downgraded.stripe_customer_id == "cus_test_123"


class TestLookupByStripeIds:
    """Test subscription lookup by Stripe IDs."""

    @pytest.mark.asyncio
    async def test_lookup_by_stripe_customer(self, db_session: AsyncSession):
        """Find subscription by stripe_customer_id."""
        user = await _create_user(db_session)
        subscription = Subscription(
            user_id=user.id, plan="pro", status="active",
            stripe_customer_id="cus_lookup_123",
        )
        db_session.add(subscription)
        await db_session.flush()

        result = await get_subscription_by_stripe_customer(db_session, "cus_lookup_123")
        assert result is not None
        assert result.id == subscription.id

    @pytest.mark.asyncio
    async def test_lookup_by_stripe_subscription(self, db_session: AsyncSession):
        """Find subscription by stripe_subscription_id."""
        user = await _create_user(db_session)
        subscription = Subscription(
            user_id=user.id, plan="business", status="active",
            stripe_subscription_id="sub_lookup_456",
        )
        db_session.add(subscription)
        await db_session.flush()

        result = await get_subscription_by_stripe_subscription(db_session, "sub_lookup_456")
        assert result is not None
        assert result.id == subscription.id

    @pytest.mark.asyncio
    async def test_lookup_not_found_returns_none(self, db_session: AsyncSession):
        """Unknown Stripe ID returns None."""
        result = await get_subscription_by_stripe_customer(db_session, "cus_nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_lookup_subscription_not_found(self, db_session: AsyncSession):
        """Unknown Stripe subscription ID returns None."""
        result = await get_subscription_by_stripe_subscription(db_session, "sub_nonexistent")
        assert result is None
