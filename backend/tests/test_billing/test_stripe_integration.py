"""Optional Stripe integration tests — hit real Stripe test mode API.

These tests are auto-skipped when STRIPE_SECRET_KEY is not set (e.g., in CI).
They run on EC2 where Stripe keys are configured in the container environment.
"""

import os

import pytest
import stripe

from app.billing.stripe_client import (
    construct_webhook_event,
    create_checkout_session,
    create_customer,
    get_subscription,
)

SKIP_REASON = "STRIPE_SECRET_KEY not set — skipping real Stripe integration tests"
pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(not os.getenv("STRIPE_SECRET_KEY"), reason=SKIP_REASON),
]


class TestStripeIntegration:
    """Real Stripe API tests — only run when STRIPE_SECRET_KEY is available."""

    async def test_create_real_customer(self):
        """Verify we can create a real Stripe customer in test mode."""
        customer = await create_customer(
            email="integration-test@villaops.test",
            name="Integration Test User",
            user_id="test-integration-user-id",
        )
        assert customer.id.startswith("cus_")
        assert customer.email == "integration-test@villaops.test"
        assert customer.metadata.get("villaops_user_id") == "test-integration-user-id"

    async def test_create_checkout_session_returns_url(self):
        """Verify checkout session creation returns a valid URL."""
        customer = await create_customer(
            email="checkout-test@villaops.test",
            name="Checkout Test User",
            user_id="test-checkout-user-id",
        )

        from app.config import settings

        if not settings.stripe_pro_price_id:
            pytest.skip("STRIPE_PRO_PRICE_ID not configured")

        session = await create_checkout_session(
            customer_id=customer.id,
            price_id=settings.stripe_pro_price_id,
            success_url="https://example.com/success",
            cancel_url="https://example.com/cancel",
        )
        assert session.id.startswith("cs_")
        assert session.url is not None
        assert "checkout.stripe.com" in session.url

    def test_construct_webhook_event_invalid_signature(self):
        """Verify signature verification rejects invalid signatures."""
        with pytest.raises(stripe.SignatureVerificationError):
            construct_webhook_event(
                payload=b'{"type": "test"}',
                sig_header="t=12345,v1=invalid_signature",
            )

    async def test_retrieve_nonexistent_subscription(self):
        """Verify proper error when retrieving a non-existent subscription."""
        with pytest.raises(stripe.InvalidRequestError):
            await get_subscription("sub_nonexistent_12345")
