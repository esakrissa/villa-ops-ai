"""Async Stripe API wrapper for VillaOps AI."""

import logging

import stripe
from stripe import StripeClient

from app.config import settings

logger = logging.getLogger(__name__)


def get_stripe_client() -> StripeClient:
    """Create a StripeClient instance with async HTTP support."""
    return StripeClient(
        settings.stripe_secret_key,
        http_client=stripe.HTTPXClient(),
    )


async def create_customer(email: str, name: str, user_id: str) -> stripe.Customer:
    """Create a Stripe customer linked to a VillaOps user."""
    client = get_stripe_client()
    logger.info("Creating Stripe customer for user %s (%s)", user_id, email)
    customer = await client.v1.customers.create_async(
        params={
            "email": email,
            "name": name,
            "metadata": {"villaops_user_id": user_id},
        }
    )
    logger.info("Created Stripe customer %s for user %s", customer.id, user_id)
    return customer


async def create_checkout_session(
    customer_id: str,
    price_id: str,
    success_url: str,
    cancel_url: str,
) -> stripe.checkout.Session:
    """Create a Stripe Checkout Session for subscription upgrade."""
    client = get_stripe_client()
    logger.info(
        "Creating checkout session for customer %s, price %s",
        customer_id,
        price_id,
    )
    return await client.v1.checkout.sessions.create_async(
        params={
            "mode": "subscription",
            "customer": customer_id,
            "line_items": [{"price": price_id, "quantity": 1}],
            "success_url": success_url,
            "cancel_url": cancel_url,
        }
    )


async def create_portal_session(
    customer_id: str, return_url: str
) -> stripe.billing_portal.Session:
    """Create a Stripe Customer Portal session for subscription management."""
    client = get_stripe_client()
    logger.info("Creating portal session for customer %s", customer_id)
    return await client.v1.billing_portal.sessions.create_async(
        params={
            "customer": customer_id,
            "return_url": return_url,
        }
    )


async def get_subscription(subscription_id: str) -> stripe.Subscription:
    """Retrieve a Stripe subscription by ID."""
    client = get_stripe_client()
    return await client.v1.subscriptions.retrieve_async(subscription_id)


def construct_webhook_event(payload: bytes, sig_header: str) -> stripe.Event:
    """Verify and construct a Stripe webhook event (synchronous)."""
    client = get_stripe_client()
    return client.construct_event(payload, sig_header, settings.stripe_webhook_secret)
