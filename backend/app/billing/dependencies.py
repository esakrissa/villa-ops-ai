"""Plan gating dependencies — enforce usage limits based on subscription plan."""

import logging
from datetime import datetime, timezone

from fastapi import Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_active_user
from app.billing.plans import PlanLimits, get_plan
from app.database import get_db
from app.models.llm_usage import LLMUsage
from app.models.property import Property
from app.models.user import User
from app.services.subscription_service import get_or_create_subscription

logger = logging.getLogger(__name__)


def _get_period_start(subscription) -> datetime:
    """Get the start of the current billing period (naive UTC)."""
    if subscription.current_period_start is not None:
        return subscription.current_period_start
    # Free plan: use first day of current month
    now = datetime.now(timezone.utc)
    return datetime(now.year, now.month, 1)  # naive UTC


async def get_plan_limits(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_active_user),
) -> PlanLimits:
    """Fetch the user's subscription and return their plan limits."""
    subscription = await get_or_create_subscription(db, user)
    return get_plan(subscription.plan)


async def check_property_limit(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_active_user),
) -> None:
    """Raise 402 if the user has reached their plan's property limit."""
    subscription = await get_or_create_subscription(db, user)
    plan = get_plan(subscription.plan)

    if plan.max_properties is None:
        return  # Unlimited

    count_result = await db.execute(
        select(func.count()).select_from(Property).where(Property.owner_id == user.id)
    )
    current_count = count_result.scalar_one()

    if current_count >= plan.max_properties:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "message": f"Property limit reached ({current_count}/{plan.max_properties}). Upgrade your plan for more properties.",
                "limit": plan.max_properties,
                "current": current_count,
                "plan": plan.name,
                "upgrade_url": "/api/v1/billing/checkout",
            },
        )


async def check_ai_query_limit(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_active_user),
) -> None:
    """Raise 402 if the user has exceeded their plan's AI query limit."""
    subscription = await get_or_create_subscription(db, user)
    plan = get_plan(subscription.plan)

    if plan.max_ai_queries_per_month is None:
        return  # Unlimited

    period_start = _get_period_start(subscription)

    count_result = await db.execute(
        select(func.count())
        .select_from(LLMUsage)
        .where(
            LLMUsage.user_id == user.id,
            LLMUsage.created_at >= period_start,
        )
    )
    current_count = count_result.scalar_one()

    if current_count >= plan.max_ai_queries_per_month:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "message": f"AI query limit reached ({current_count}/{plan.max_ai_queries_per_month}). Upgrade your plan for more queries.",
                "limit": plan.max_ai_queries_per_month,
                "current": current_count,
                "plan": plan.name,
                "upgrade_url": "/api/v1/billing/checkout",
            },
        )


async def check_notification_access(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_active_user),
) -> None:
    """Raise 402 if the user's plan does not include notifications."""
    subscription = await get_or_create_subscription(db, user)
    plan = get_plan(subscription.plan)

    if not plan.has_notifications:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "message": "Notifications require a Pro or Business plan.",
                "plan": plan.name,
                "upgrade_url": "/api/v1/billing/checkout",
            },
        )
