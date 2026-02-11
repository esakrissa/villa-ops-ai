"""Stripe webhook event handlers — process subscription lifecycle events."""

import logging
from datetime import datetime

import stripe
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing.plans import get_plan_by_price_id
from app.billing.stripe_client import get_subscription
from app.services.subscription_service import (
    downgrade_to_free,
    get_subscription_by_stripe_customer,
    get_subscription_by_stripe_subscription,
    update_subscription_from_stripe,
)

logger = logging.getLogger(__name__)


def _ts_to_naive(ts: int | None) -> datetime | None:
    """Convert Stripe Unix timestamp to naive UTC datetime."""
    if ts is None:
        return None
    return datetime.utcfromtimestamp(ts)


def _get_price_id_from_subscription(stripe_sub: stripe.Subscription) -> str | None:
    """Extract the first price ID from a Stripe subscription's items."""
    if stripe_sub.items and stripe_sub.items.data:
        return stripe_sub.items.data[0].price.id
    return None


async def handle_checkout_session_completed(
    db: AsyncSession, event: stripe.Event
) -> None:
    """Handle checkout.session.completed — activate new subscription."""
    session = event.data.object
    customer_id = session.customer
    subscription_id = session.subscription

    if not subscription_id:
        logger.info("Checkout session %s has no subscription (one-time?), skipping", session.id)
        return

    subscription = await get_subscription_by_stripe_customer(db, customer_id)
    if subscription is None:
        logger.warning(
            "No local subscription found for Stripe customer %s (checkout %s)",
            customer_id,
            session.id,
        )
        return

    # Fetch full subscription from Stripe to get price and period info
    stripe_sub = await get_subscription(subscription_id)
    price_id = _get_price_id_from_subscription(stripe_sub)
    plan = get_plan_by_price_id(price_id) if price_id else None

    if plan is None:
        logger.warning("Unknown price ID %s in subscription %s", price_id, subscription_id)
        plan = "free"

    await update_subscription_from_stripe(
        db,
        subscription=subscription,
        stripe_subscription_id=subscription_id,
        plan=plan,
        status="active",
        current_period_start=_ts_to_naive(stripe_sub.current_period_start),
        current_period_end=_ts_to_naive(stripe_sub.current_period_end),
        cancel_at_period_end=stripe_sub.cancel_at_period_end or False,
    )
    logger.info(
        "Checkout completed: subscription %s activated on plan %s",
        subscription_id,
        plan,
    )


async def handle_invoice_paid(db: AsyncSession, event: stripe.Event) -> None:
    """Handle invoice.paid — confirm active status and update billing period."""
    invoice = event.data.object
    subscription_id = getattr(invoice, "subscription", None)

    if not subscription_id:
        logger.info("Invoice %s has no subscription (one-time), skipping", invoice.id)
        return

    subscription = await get_subscription_by_stripe_subscription(db, subscription_id)
    if subscription is None:
        logger.warning(
            "No local subscription found for Stripe subscription %s (invoice %s)",
            subscription_id,
            invoice.id,
        )
        return

    # Fetch full subscription from Stripe to get current period
    stripe_sub = await get_subscription(subscription_id)
    price_id = _get_price_id_from_subscription(stripe_sub)
    plan = get_plan_by_price_id(price_id) if price_id else subscription.plan

    if plan is None:
        plan = subscription.plan

    await update_subscription_from_stripe(
        db,
        subscription=subscription,
        stripe_subscription_id=subscription_id,
        plan=plan,
        status="active",
        current_period_start=_ts_to_naive(stripe_sub.current_period_start),
        current_period_end=_ts_to_naive(stripe_sub.current_period_end),
        cancel_at_period_end=stripe_sub.cancel_at_period_end or False,
    )
    logger.info("Invoice paid: subscription %s confirmed active", subscription_id)


async def handle_subscription_updated(
    db: AsyncSession, event: stripe.Event
) -> None:
    """Handle customer.subscription.updated — sync plan, status, and period."""
    stripe_sub = event.data.object
    subscription_id = stripe_sub.id
    customer_id = stripe_sub.customer

    # Try lookup by subscription ID first, then by customer ID
    subscription = await get_subscription_by_stripe_subscription(db, subscription_id)
    if subscription is None:
        subscription = await get_subscription_by_stripe_customer(db, customer_id)

    if subscription is None:
        logger.warning(
            "No local subscription found for Stripe subscription %s (customer %s)",
            subscription_id,
            customer_id,
        )
        return

    price_id = _get_price_id_from_subscription(stripe_sub)
    plan = get_plan_by_price_id(price_id) if price_id else subscription.plan

    if plan is None:
        plan = subscription.plan

    await update_subscription_from_stripe(
        db,
        subscription=subscription,
        stripe_subscription_id=subscription_id,
        plan=plan,
        status=stripe_sub.status,
        current_period_start=_ts_to_naive(stripe_sub.current_period_start),
        current_period_end=_ts_to_naive(stripe_sub.current_period_end),
        cancel_at_period_end=stripe_sub.cancel_at_period_end or False,
    )
    logger.info(
        "Subscription updated: %s → plan=%s, status=%s",
        subscription_id,
        plan,
        stripe_sub.status,
    )


async def handle_subscription_deleted(
    db: AsyncSession, event: stripe.Event
) -> None:
    """Handle customer.subscription.deleted — downgrade to free tier."""
    stripe_sub = event.data.object
    subscription_id = stripe_sub.id

    subscription = await get_subscription_by_stripe_subscription(db, subscription_id)
    if subscription is None:
        logger.warning(
            "No local subscription found for Stripe subscription %s (delete event)",
            subscription_id,
        )
        return

    await downgrade_to_free(db, subscription)
    logger.info("Subscription deleted: %s downgraded to free tier", subscription_id)


async def handle_invoice_payment_failed(
    db: AsyncSession, event: stripe.Event
) -> None:
    """Handle invoice.payment_failed — mark subscription as past_due."""
    invoice = event.data.object
    subscription_id = getattr(invoice, "subscription", None)

    if not subscription_id:
        logger.info(
            "Invoice %s has no subscription (one-time), skipping payment failure",
            invoice.id,
        )
        return

    subscription = await get_subscription_by_stripe_subscription(db, subscription_id)
    if subscription is None:
        logger.warning(
            "No local subscription found for Stripe subscription %s (payment failed)",
            subscription_id,
        )
        return

    subscription.status = "past_due"
    await db.flush()
    logger.info(
        "Payment failed: subscription %s marked as past_due",
        subscription_id,
    )
