"""Extended subscription service tests — edge cases not covered in test_billing/."""

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.passwords import hash_password
from app.models.subscription import Subscription
from app.models.user import User
from app.services.subscription_service import (
    downgrade_to_free,
    ensure_stripe_customer,
    get_or_create_subscription,
    get_subscription_by_stripe_customer,
    get_subscription_by_stripe_subscription,
    update_subscription_from_stripe,
)


async def _create_user_with_sub(
    db_session: AsyncSession,
    plan: str = "free",
    stripe_customer_id: str | None = None,
) -> tuple[User, Subscription]:
    """Helper: create a user with a subscription."""
    unique = uuid.uuid4().hex[:8]
    user = User(
        email=f"ext-svc-{unique}@test.com",
        hashed_password=hash_password("testpass"),
        name="Extended Test User",
        auth_provider="local",
        is_active=True,
        role="manager",
    )
    db_session.add(user)
    await db_session.flush()

    sub = Subscription(
        user_id=user.id,
        plan=plan,
        status="active",
        stripe_customer_id=stripe_customer_id,
    )
    db_session.add(sub)
    await db_session.flush()
    return user, sub


class TestEnsureStripeCustomer:
    """Test ensure_stripe_customer — creates Stripe customer if needed."""

    async def test_returns_existing_customer_id(self, db_session: AsyncSession):
        user, sub = await _create_user_with_sub(
            db_session, plan="pro", stripe_customer_id="cus_existing_abc"
        )
        result = await ensure_stripe_customer(db_session, user, sub)
        assert result == "cus_existing_abc"

    @patch("app.services.subscription_service.create_customer", new_callable=AsyncMock)
    async def test_creates_new_stripe_customer(
        self, mock_create_customer: AsyncMock, db_session: AsyncSession
    ):
        mock_create_customer.return_value = AsyncMock(id="cus_new_xyz")

        user, sub = await _create_user_with_sub(db_session, plan="free")
        assert sub.stripe_customer_id is None

        result = await ensure_stripe_customer(db_session, user, sub)
        assert result == "cus_new_xyz"
        assert sub.stripe_customer_id == "cus_new_xyz"

        mock_create_customer.assert_called_once_with(
            email=user.email,
            name=user.name or user.email,
            user_id=str(user.id),
        )


class TestGetOrCreateIdempotent:
    """Test get_or_create_subscription edge cases."""

    async def test_idempotent_returns_same(self, db_session: AsyncSession):
        """Calling get_or_create twice returns the same subscription."""
        unique = uuid.uuid4().hex[:8]
        user = User(
            email=f"idempotent-{unique}@test.com",
            hashed_password=hash_password("testpass"),
            name="Idempotent User",
            auth_provider="local",
            is_active=True,
            role="manager",
        )
        db_session.add(user)
        await db_session.flush()

        sub1 = await get_or_create_subscription(db_session, user)
        sub2 = await get_or_create_subscription(db_session, user)
        assert sub1.id == sub2.id
        assert sub1.plan == "free"


class TestUpdateSubscriptionEdgeCases:
    """Test update_subscription_from_stripe edge cases."""

    async def test_update_without_period_dates(self, db_session: AsyncSession):
        """Update without period dates keeps them as None."""
        user, sub = await _create_user_with_sub(db_session, plan="free")

        updated = await update_subscription_from_stripe(
            db_session,
            subscription=sub,
            stripe_subscription_id="sub_no_period",
            plan="pro",
            status="active",
        )
        assert updated.plan == "pro"
        assert updated.current_period_start is None
        assert updated.current_period_end is None

    async def test_update_changes_plan_and_status(self, db_session: AsyncSession):
        """Update can change both plan and status."""
        user, sub = await _create_user_with_sub(db_session, plan="pro")

        updated = await update_subscription_from_stripe(
            db_session,
            subscription=sub,
            stripe_subscription_id="sub_upgrade",
            plan="business",
            status="active",
            current_period_start=datetime(2026, 2, 1),
            current_period_end=datetime(2026, 3, 1),
        )
        assert updated.plan == "business"
        assert updated.stripe_subscription_id == "sub_upgrade"


class TestDowngradeToFreePreservesCustomerId:
    """Verify downgrade_to_free preserves stripe_customer_id."""

    async def test_preserves_stripe_customer_id(self, db_session: AsyncSession):
        user, sub = await _create_user_with_sub(
            db_session, plan="business", stripe_customer_id="cus_keep_me"
        )
        sub.stripe_subscription_id = "sub_to_cancel"
        sub.current_period_start = datetime(2026, 1, 1)
        sub.current_period_end = datetime(2026, 2, 1)
        await db_session.flush()

        downgraded = await downgrade_to_free(db_session, sub)
        assert downgraded.plan == "free"
        assert downgraded.stripe_customer_id == "cus_keep_me"
        assert downgraded.stripe_subscription_id is None
