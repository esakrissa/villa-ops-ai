"""Subscription service — CRUD operations for user subscriptions."""

import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing.plans import get_plan
from app.billing.stripe_client import create_customer
from app.models.subscription import Subscription
from app.models.user import User

logger = logging.getLogger(__name__)


async def get_or_create_subscription(
    db: AsyncSession, user: User
) -> Subscription:
    """Get existing subscription or create a free-tier one for the user."""
    result = await db.execute(
        select(Subscription).where(Subscription.user_id == user.id)
    )
    subscription = result.scalar_one_or_none()

    if subscription is not None:
        return subscription

    logger.info("Creating free-tier subscription for user %s", user.id)
    subscription = Subscription(
        user_id=user.id,
        plan="free",
        status="active",
    )
    db.add(subscription)
    await db.flush()
    return subscription


async def get_subscription_by_stripe_customer(
    db: AsyncSession, stripe_customer_id: str
) -> Subscription | None:
    """Look up subscription by Stripe customer ID (used by webhooks)."""
    result = await db.execute(
        select(Subscription).where(
            Subscription.stripe_customer_id == stripe_customer_id
        )
    )
    return result.scalar_one_or_none()


async def get_subscription_by_stripe_subscription(
    db: AsyncSession, stripe_subscription_id: str
) -> Subscription | None:
    """Look up subscription by Stripe subscription ID (used by webhooks)."""
    result = await db.execute(
        select(Subscription).where(
            Subscription.stripe_subscription_id == stripe_subscription_id
        )
    )
    return result.scalar_one_or_none()


async def ensure_stripe_customer(
    db: AsyncSession, user: User, subscription: Subscription
) -> str:
    """Ensure the user has a Stripe customer ID. Create one if missing."""
    if subscription.stripe_customer_id:
        return subscription.stripe_customer_id

    customer = await create_customer(
        email=user.email,
        name=user.name or user.email,
        user_id=str(user.id),
    )
    subscription.stripe_customer_id = customer.id
    await db.flush()
    logger.info(
        "Linked Stripe customer %s to user %s", customer.id, user.id
    )
    return customer.id


async def update_subscription_from_stripe(
    db: AsyncSession,
    subscription: Subscription,
    stripe_subscription_id: str,
    plan: str,
    status: str,
    current_period_start: datetime | None = None,
    current_period_end: datetime | None = None,
    cancel_at_period_end: bool = False,
) -> Subscription:
    """Update local subscription record from Stripe webhook data."""
    subscription.stripe_subscription_id = stripe_subscription_id
    subscription.plan = plan
    subscription.status = status
    subscription.current_period_start = current_period_start
    subscription.current_period_end = current_period_end
    subscription.cancel_at_period_end = cancel_at_period_end
    await db.flush()

    plan_info = get_plan(plan)
    logger.info(
        "Updated subscription %s: plan=%s (%s), status=%s",
        subscription.id,
        plan,
        plan_info.display_name,
        status,
    )
    return subscription


async def downgrade_to_free(
    db: AsyncSession, subscription: Subscription
) -> Subscription:
    """Downgrade subscription to free tier (called on cancellation)."""
    subscription.stripe_subscription_id = None
    subscription.plan = "free"
    subscription.status = "active"
    subscription.current_period_start = None
    subscription.current_period_end = None
    subscription.cancel_at_period_end = False
    await db.flush()

    logger.info(
        "Downgraded subscription %s (user %s) to free tier",
        subscription.id,
        subscription.user_id,
    )
    return subscription
