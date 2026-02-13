"""Tests for Stripe webhook handler functions with mocked Stripe events."""

import uuid
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.passwords import hash_password
from app.billing.webhooks import (
    _get_price_id_from_subscription,
    _ts_to_naive,
    handle_checkout_session_completed,
    handle_invoice_paid,
    handle_invoice_payment_failed,
    handle_subscription_deleted,
    handle_subscription_updated,
)
from app.models.subscription import Subscription
from app.models.user import User


async def _create_user_with_subscription(
    db_session: AsyncSession,
    plan: str = "free",
    stripe_customer_id: str | None = None,
    stripe_subscription_id: str | None = None,
) -> tuple[User, Subscription]:
    """Create a user with a subscription for webhook testing."""
    unique = uuid.uuid4().hex[:8]
    user = User(
        email=f"webhook-{unique}@test.com",
        hashed_password=hash_password("testpass"),
        name="Webhook Test User",
        auth_provider="local",
        is_active=True,
        role="manager",
    )
    db_session.add(user)
    await db_session.flush()

    subscription = Subscription(
        user_id=user.id,
        plan=plan,
        status="active",
        stripe_customer_id=stripe_customer_id,
        stripe_subscription_id=stripe_subscription_id,
    )
    db_session.add(subscription)
    await db_session.flush()
    return user, subscription


class _StripeObj(SimpleNamespace):
    """SimpleNamespace with bracket notation support (like Stripe API objects).

    Stripe API 2025-08-27 (basil) changed subscription.items to require
    bracket notation to avoid collision with Python dict .items().
    """

    def __getitem__(self, key: str):
        return getattr(self, key)


def _make_event(event_type: str, data_object: dict) -> _StripeObj:
    """Create a fake Stripe Event-like object."""
    obj = _StripeObj(**data_object)
    return _StripeObj(
        type=event_type,
        id=f"evt_test_{uuid.uuid4().hex[:8]}",
        data=_StripeObj(object=obj),
    )


def _make_stripe_sub(
    price_id: str,
    status: str = "active",
    period_start: int = 1700000000,
    period_end: int = 1702600000,
    cancel_at_period_end: bool = False,
    sub_id: str = "sub_test_123",
    customer: str = "cus_test_123",
) -> _StripeObj:
    """Create a fake Stripe Subscription object."""
    # Stripe API 2025-08-27 (basil): current_period_start/end moved to item level
    return _StripeObj(
        id=sub_id,
        customer=customer,
        status=status,
        cancel_at_period_end=cancel_at_period_end,
        items=_StripeObj(
            data=[_StripeObj(
                price=_StripeObj(id=price_id),
                current_period_start=period_start,
                current_period_end=period_end,
            )]
        ),
    )


# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------


class TestHelpers:
    """Test webhook helper functions."""

    def test_ts_to_naive_with_value(self):
        """Convert Unix timestamp to naive datetime."""
        result = _ts_to_naive(1700000000)
        assert isinstance(result, datetime)
        assert result.tzinfo is None

    def test_ts_to_naive_with_none(self):
        """None timestamp returns None."""
        assert _ts_to_naive(None) is None

    def test_get_price_id_from_subscription(self):
        """Extract price ID from subscription items."""
        fake_sub = _make_stripe_sub("price_pro_123")
        result = _get_price_id_from_subscription(fake_sub)
        assert result == "price_pro_123"

    def test_get_price_id_empty_items(self):
        """Return None if no items."""
        fake_sub = _StripeObj(items=_StripeObj(data=[]))
        result = _get_price_id_from_subscription(fake_sub)
        assert result is None

    def test_get_price_id_no_items(self):
        """Return None if items is None."""
        fake_sub = _StripeObj(items=None)
        result = _get_price_id_from_subscription(fake_sub)
        assert result is None


# ---------------------------------------------------------------------------
# checkout.session.completed handler
# ---------------------------------------------------------------------------


class TestHandleCheckoutSessionCompleted:
    """Test handle_checkout_session_completed."""

    @pytest.mark.asyncio
    async def test_activates_subscription(self, db_session: AsyncSession):
        """Checkout completed should activate subscription with correct plan."""
        _, subscription = await _create_user_with_subscription(
            db_session, plan="free", stripe_customer_id="cus_checkout_123",
        )

        fake_stripe_sub = _make_stripe_sub(
            price_id="price_test_pro",
            sub_id="sub_checkout_activated",
            customer="cus_checkout_123",
        )

        event = _make_event("checkout.session.completed", {
            "id": "cs_test_session",
            "customer": "cus_checkout_123",
            "subscription": "sub_checkout_activated",
        })

        with (
            patch(
                "app.billing.webhooks.get_subscription",
                new_callable=AsyncMock,
                return_value=fake_stripe_sub,
            ),
            patch(
                "app.billing.webhooks.get_plan_by_price_id",
                return_value="pro",
            ),
        ):
            await handle_checkout_session_completed(db_session, event)

        await db_session.refresh(subscription)
        assert subscription.plan == "pro"
        assert subscription.status == "active"
        assert subscription.stripe_subscription_id == "sub_checkout_activated"

    @pytest.mark.asyncio
    async def test_no_subscription_in_event(self, db_session: AsyncSession):
        """Skip if checkout session has no subscription (one-time payment)."""
        event = _make_event("checkout.session.completed", {
            "id": "cs_one_time",
            "customer": "cus_test_123",
            "subscription": None,
        })
        # Should not raise
        await handle_checkout_session_completed(db_session, event)

    @pytest.mark.asyncio
    async def test_no_local_subscription(self, db_session: AsyncSession):
        """Log warning if no local subscription matches the Stripe customer."""
        event = _make_event("checkout.session.completed", {
            "id": "cs_orphan",
            "customer": "cus_unknown_999",
            "subscription": "sub_orphan_123",
        })
        # Should not raise
        await handle_checkout_session_completed(db_session, event)


# ---------------------------------------------------------------------------
# invoice.paid handler
# ---------------------------------------------------------------------------


class TestHandleInvoicePaid:
    """Test handle_invoice_paid."""

    @pytest.mark.asyncio
    async def test_updates_period(self, db_session: AsyncSession):
        """Invoice paid should update billing period."""
        _, subscription = await _create_user_with_subscription(
            db_session,
            plan="pro",
            stripe_subscription_id="sub_invoice_123",
        )

        fake_stripe_sub = _make_stripe_sub(
            price_id="price_test_pro",
            period_start=1706745600,  # 2024-02-01
            period_end=1709251200,    # 2024-03-01
            sub_id="sub_invoice_123",
        )

        event = _make_event("invoice.paid", {
            "id": "in_test_paid",
            "subscription": "sub_invoice_123",
        })

        with (
            patch(
                "app.billing.webhooks.get_subscription",
                new_callable=AsyncMock,
                return_value=fake_stripe_sub,
            ),
            patch(
                "app.billing.webhooks.get_plan_by_price_id",
                return_value="pro",
            ),
        ):
            await handle_invoice_paid(db_session, event)

        await db_session.refresh(subscription)
        assert subscription.status == "active"
        assert subscription.current_period_start is not None
        assert subscription.current_period_end is not None

    @pytest.mark.asyncio
    async def test_no_subscription_id_in_invoice(self, db_session: AsyncSession):
        """Skip if invoice has no subscription (one-time charge)."""
        event = _make_event("invoice.paid", {
            "id": "in_one_time",
        })
        # getattr returns None for missing 'subscription'
        event.data.object.subscription = None
        # Should not raise
        await handle_invoice_paid(db_session, event)

    @pytest.mark.asyncio
    async def test_no_local_subscription(self, db_session: AsyncSession):
        """Log warning if subscription not found locally."""
        event = _make_event("invoice.paid", {
            "id": "in_orphan",
            "subscription": "sub_unknown_999",
        })
        # Should not raise
        await handle_invoice_paid(db_session, event)


# ---------------------------------------------------------------------------
# customer.subscription.updated handler
# ---------------------------------------------------------------------------


class TestHandleSubscriptionUpdated:
    """Test handle_subscription_updated."""

    @pytest.mark.asyncio
    async def test_syncs_plan_and_status(self, db_session: AsyncSession):
        """Subscription update should sync plan, status, and period."""
        _, subscription = await _create_user_with_subscription(
            db_session,
            plan="pro",
            stripe_customer_id="cus_update_123",
            stripe_subscription_id="sub_update_123",
        )

        fake_stripe_sub = _make_stripe_sub(
            price_id="price_test_business",
            status="active",
            period_start=1706745600,
            period_end=1709251200,
            cancel_at_period_end=False,
            sub_id="sub_update_123",
            customer="cus_update_123",
        )

        event = _make_event("customer.subscription.updated", {
            "id": "sub_update_123",
            "customer": "cus_update_123",
            "status": "active",
            "current_period_start": 1706745600,
            "current_period_end": 1709251200,
            "cancel_at_period_end": False,
            "items": _StripeObj(
                data=[_StripeObj(price=_StripeObj(id="price_test_business"))]
            ),
        })

        with patch(
            "app.billing.webhooks.get_plan_by_price_id",
            return_value="business",
        ):
            await handle_subscription_updated(db_session, event)

        await db_session.refresh(subscription)
        assert subscription.plan == "business"
        assert subscription.status == "active"

    @pytest.mark.asyncio
    async def test_lookup_by_customer_id_fallback(self, db_session: AsyncSession):
        """Falls back to customer ID lookup if subscription ID not found."""
        _, subscription = await _create_user_with_subscription(
            db_session,
            plan="free",
            stripe_customer_id="cus_fallback_123",
        )

        event = _make_event("customer.subscription.updated", {
            "id": "sub_new_123",
            "customer": "cus_fallback_123",
            "status": "active",
            "current_period_start": 1706745600,
            "current_period_end": 1709251200,
            "cancel_at_period_end": False,
            "items": _StripeObj(
                data=[_StripeObj(price=_StripeObj(id="price_test_pro"))]
            ),
        })

        with patch(
            "app.billing.webhooks.get_plan_by_price_id",
            return_value="pro",
        ):
            await handle_subscription_updated(db_session, event)

        await db_session.refresh(subscription)
        assert subscription.plan == "pro"
        assert subscription.stripe_subscription_id == "sub_new_123"

    @pytest.mark.asyncio
    async def test_no_local_subscription(self, db_session: AsyncSession):
        """Log warning if no local subscription found."""
        event = _make_event("customer.subscription.updated", {
            "id": "sub_orphan_123",
            "customer": "cus_orphan_123",
            "status": "active",
            "current_period_start": 1706745600,
            "current_period_end": 1709251200,
            "cancel_at_period_end": False,
            "items": _StripeObj(
                data=[_StripeObj(price=_StripeObj(id="price_test_pro"))]
            ),
        })
        # Should not raise
        await handle_subscription_updated(db_session, event)


# ---------------------------------------------------------------------------
# customer.subscription.deleted handler
# ---------------------------------------------------------------------------


class TestHandleSubscriptionDeleted:
    """Test handle_subscription_deleted."""

    @pytest.mark.asyncio
    async def test_downgrades_to_free(self, db_session: AsyncSession):
        """Subscription deletion should downgrade to free tier."""
        _, subscription = await _create_user_with_subscription(
            db_session,
            plan="pro",
            stripe_subscription_id="sub_delete_123",
        )

        event = _make_event("customer.subscription.deleted", {
            "id": "sub_delete_123",
            "customer": "cus_test_123",
        })

        await handle_subscription_deleted(db_session, event)

        await db_session.refresh(subscription)
        assert subscription.plan == "free"
        assert subscription.status == "active"
        assert subscription.stripe_subscription_id is None

    @pytest.mark.asyncio
    async def test_no_local_subscription(self, db_session: AsyncSession):
        """Log warning if subscription not found locally."""
        event = _make_event("customer.subscription.deleted", {
            "id": "sub_unknown_del",
            "customer": "cus_unknown_del",
        })
        # Should not raise
        await handle_subscription_deleted(db_session, event)


# ---------------------------------------------------------------------------
# invoice.payment_failed handler
# ---------------------------------------------------------------------------


class TestHandleInvoicePaymentFailed:
    """Test handle_invoice_payment_failed."""

    @pytest.mark.asyncio
    async def test_marks_past_due(self, db_session: AsyncSession):
        """Payment failure should mark subscription as past_due."""
        _, subscription = await _create_user_with_subscription(
            db_session,
            plan="pro",
            stripe_subscription_id="sub_fail_123",
        )

        event = _make_event("invoice.payment_failed", {
            "id": "in_failed",
            "subscription": "sub_fail_123",
        })

        await handle_invoice_payment_failed(db_session, event)

        await db_session.refresh(subscription)
        assert subscription.status == "past_due"

    @pytest.mark.asyncio
    async def test_no_subscription_id(self, db_session: AsyncSession):
        """Skip if invoice has no subscription."""
        event = _make_event("invoice.payment_failed", {
            "id": "in_one_time_fail",
        })
        event.data.object.subscription = None
        # Should not raise
        await handle_invoice_payment_failed(db_session, event)

    @pytest.mark.asyncio
    async def test_no_local_subscription(self, db_session: AsyncSession):
        """Log warning if subscription not found locally."""
        event = _make_event("invoice.payment_failed", {
            "id": "in_orphan_fail",
            "subscription": "sub_orphan_fail",
        })
        # Should not raise
        await handle_invoice_payment_failed(db_session, event)
