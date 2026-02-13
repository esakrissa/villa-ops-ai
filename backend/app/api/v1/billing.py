"""Billing API endpoints — subscription management, Stripe Checkout, and Customer Portal."""

import logging
from datetime import datetime

import stripe
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, get_db
from app.billing.plans import PLANS, get_plan
from app.billing.stripe_client import (
    create_checkout_session,
    create_portal_session,
)
from app.config import settings
from app.models.llm_usage import LLMUsage
from app.models.property import Property
from app.models.user import User
from app.schemas.billing import (
    CheckoutRequest,
    CheckoutResponse,
    PlanResponse,
    PlansListResponse,
    PortalRequest,
    PortalResponse,
    SubscriptionResponse,
    UsageResponse,
)
from app.services.subscription_service import (
    ensure_stripe_customer,
    get_or_create_subscription,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/billing", tags=["billing"])


@router.get("/plans", response_model=PlansListResponse)
async def list_plans() -> PlansListResponse:
    """List available plans (public — no auth required)."""
    return PlansListResponse(
        plans=[
            PlanResponse(
                name=p.name,
                display_name=p.display_name,
                max_properties=p.max_properties,
                max_ai_queries_per_month=p.max_ai_queries_per_month,
                has_analytics_export=p.has_analytics_export,
                has_notifications=p.has_notifications,
                price_monthly_cents=p.price_monthly_cents,
            )
            for p in PLANS.values()
        ]
    )


@router.get("/subscription", response_model=SubscriptionResponse)
async def get_subscription(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SubscriptionResponse:
    """Get current subscription plan and usage stats."""
    subscription = await get_or_create_subscription(db, current_user)
    plan = get_plan(subscription.plan)

    # Determine billing period start (naive UTC to match DB column)
    now = datetime.utcnow()
    period_start = subscription.current_period_start or datetime(
        now.year, now.month, 1
    )

    # Count AI queries used this billing period
    result = await db.execute(
        select(func.count())
        .select_from(LLMUsage)
        .where(
            LLMUsage.user_id == current_user.id,
            LLMUsage.created_at >= period_start,
        )
    )
    ai_queries_used = result.scalar_one()

    # Count properties owned
    result = await db.execute(
        select(func.count())
        .select_from(Property)
        .where(Property.owner_id == current_user.id)
    )
    properties_used = result.scalar_one()

    return SubscriptionResponse(
        plan=PlanResponse(
            name=plan.name,
            display_name=plan.display_name,
            max_properties=plan.max_properties,
            max_ai_queries_per_month=plan.max_ai_queries_per_month,
            has_analytics_export=plan.has_analytics_export,
            has_notifications=plan.has_notifications,
            price_monthly_cents=plan.price_monthly_cents,
        ),
        status=subscription.status,
        stripe_subscription_id=subscription.stripe_subscription_id,
        current_period_start=subscription.current_period_start,
        current_period_end=subscription.current_period_end,
        cancel_at_period_end=subscription.cancel_at_period_end,
        usage=UsageResponse(
            ai_queries_used=ai_queries_used,
            ai_queries_limit=plan.max_ai_queries_per_month,
            properties_used=properties_used,
            properties_limit=plan.max_properties,
        ),
    )


@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout(
    body: CheckoutRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> CheckoutResponse:
    """Create a Stripe Checkout session for subscription upgrade."""
    # Validate plan
    if body.plan not in ("pro", "business"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid plan. Choose 'pro' or 'business'.",
        )

    plan = get_plan(body.plan)
    if not plan.stripe_price_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Stripe price ID not configured for plan.",
        )

    # Ensure Stripe customer exists
    subscription = await get_or_create_subscription(db, current_user)
    customer_id = await ensure_stripe_customer(db, current_user, subscription)

    # Build URLs
    success_url = (
        body.success_url
        or f"{settings.frontend_url}/billing?session_id={{CHECKOUT_SESSION_ID}}"
    )
    cancel_url = body.cancel_url or f"{settings.frontend_url}/pricing"

    try:
        session = await create_checkout_session(
            customer_id=customer_id,
            price_id=plan.stripe_price_id,
            success_url=success_url,
            cancel_url=cancel_url,
        )
    except stripe.StripeError as e:
        logger.error("Stripe checkout error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(e),
        ) from e

    await db.commit()

    return CheckoutResponse(
        checkout_url=session.url,
        session_id=session.id,
    )


@router.post("/portal", response_model=PortalResponse)
async def create_portal(
    body: PortalRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> PortalResponse:
    """Create a Stripe Customer Portal session for subscription management."""
    subscription = await get_or_create_subscription(db, current_user)

    if not subscription.stripe_customer_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No Stripe customer found. Subscribe first.",
        )

    return_url = body.return_url or f"{settings.frontend_url}/billing"

    try:
        session = await create_portal_session(
            customer_id=subscription.stripe_customer_id,
            return_url=return_url,
        )
    except stripe.StripeError as e:
        logger.error("Stripe portal error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(e),
        ) from e

    return PortalResponse(portal_url=session.url)
