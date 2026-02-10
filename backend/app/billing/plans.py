"""Plan definitions — pricing tiers and usage limits."""

from dataclasses import dataclass

from app.config import settings


@dataclass(frozen=True)
class PlanLimits:
    """Usage limits for a subscription plan."""

    name: str
    display_name: str
    max_properties: int | None  # None = unlimited
    max_ai_queries_per_month: int | None  # None = unlimited
    has_analytics_export: bool
    has_notifications: bool
    price_monthly_cents: int  # in cents (e.g., 2900 = $29.00)
    stripe_price_id: str | None  # None for free tier


PLANS: dict[str, PlanLimits] = {
    "free": PlanLimits(
        name="free",
        display_name="Free",
        max_properties=1,
        max_ai_queries_per_month=50,
        has_analytics_export=False,
        has_notifications=False,
        price_monthly_cents=0,
        stripe_price_id=None,
    ),
    "pro": PlanLimits(
        name="pro",
        display_name="Pro",
        max_properties=5,
        max_ai_queries_per_month=500,
        has_analytics_export=True,
        has_notifications=True,
        price_monthly_cents=2900,
        stripe_price_id=settings.stripe_pro_price_id or None,
    ),
    "business": PlanLimits(
        name="business",
        display_name="Business",
        max_properties=None,
        max_ai_queries_per_month=None,
        has_analytics_export=True,
        has_notifications=True,
        price_monthly_cents=7900,
        stripe_price_id=settings.stripe_business_price_id or None,
    ),
}

VALID_PLAN_NAMES: set[str] = set(PLANS.keys())


def get_plan(plan_name: str) -> PlanLimits:
    """Get plan limits by name. Defaults to free if unknown."""
    return PLANS.get(plan_name, PLANS["free"])


def get_plan_by_price_id(price_id: str) -> str | None:
    """Reverse lookup: Stripe price ID -> plan name. Returns None if not found."""
    for plan in PLANS.values():
        if plan.stripe_price_id and plan.stripe_price_id == price_id:
            return plan.name
    return None
