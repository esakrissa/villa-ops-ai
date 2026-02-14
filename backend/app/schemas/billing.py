"""Pydantic v2 request/response schemas for billing endpoints."""

from datetime import datetime

from pydantic import BaseModel

# --- Request schemas ---


class CheckoutRequest(BaseModel):
    """Request to create a Stripe Checkout session."""

    plan: str  # "pro" or "business"
    success_url: str | None = None
    cancel_url: str | None = None


class UpgradeRequest(BaseModel):
    """Request to upgrade/downgrade an existing subscription in-place."""

    plan: str  # "pro" or "business"


class PortalRequest(BaseModel):
    """Request to create a Stripe Customer Portal session."""

    return_url: str | None = None


# --- Response schemas ---


class PlanResponse(BaseModel):
    """Plan details for display."""

    name: str
    display_name: str
    max_properties: int | None
    max_ai_queries_per_month: int | None
    has_analytics_export: bool
    has_notifications: bool
    price_monthly_cents: int


class UsageResponse(BaseModel):
    """Current billing period usage stats."""

    ai_queries_used: int
    ai_queries_limit: int | None  # None = unlimited
    properties_used: int
    properties_limit: int | None  # None = unlimited


class SubscriptionResponse(BaseModel):
    """Full subscription status + usage for the authenticated user."""

    plan: PlanResponse
    status: str
    stripe_subscription_id: str | None
    current_period_start: datetime | None
    current_period_end: datetime | None
    cancel_at_period_end: bool
    usage: UsageResponse


class CheckoutResponse(BaseModel):
    """Stripe Checkout session URL returned to frontend."""

    checkout_url: str
    session_id: str


class PortalResponse(BaseModel):
    """Stripe Customer Portal URL returned to frontend."""

    portal_url: str


class UpgradeResponse(BaseModel):
    """Result of an in-place subscription upgrade."""

    plan: str
    status: str


class PlansListResponse(BaseModel):
    """All available plans."""

    plans: list[PlanResponse]
