"""Tests for billing API endpoints with mocked Stripe calls."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import create_token_pair
from app.auth.passwords import hash_password
from app.models.subscription import Subscription
from app.models.user import User


async def _create_user_with_plan(
    db_session: AsyncSession,
    plan: str,
    stripe_customer_id: str | None = None,
) -> tuple[User, dict[str, str]]:
    """Create a user with a specific plan and return (user, auth_headers)."""
    unique = uuid.uuid4().hex[:8]
    user = User(
        email=f"billing-{unique}@test.com",
        hashed_password=hash_password("testpass"),
        name="Billing Test User",
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
    )
    db_session.add(subscription)
    await db_session.flush()

    tokens = create_token_pair(str(user.id))
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    return user, headers


class TestListPlans:
    """Test GET /api/v1/billing/plans."""

    @pytest.mark.asyncio
    async def test_list_plans_returns_3_plans(self, client: AsyncClient):
        """Should return all 3 plans."""
        response = await client.get("/api/v1/billing/plans")
        assert response.status_code == 200
        plans = response.json()["plans"]
        assert len(plans) == 3
        plan_names = {p["name"] for p in plans}
        assert plan_names == {"free", "pro", "business"}

    @pytest.mark.asyncio
    async def test_list_plans_no_auth_required(self, client: AsyncClient):
        """Plans endpoint is public, no auth needed."""
        response = await client.get("/api/v1/billing/plans")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_plan_details_structure(self, client: AsyncClient):
        """Each plan has the expected fields."""
        response = await client.get("/api/v1/billing/plans")
        plans = response.json()["plans"]
        for plan in plans:
            assert "name" in plan
            assert "display_name" in plan
            assert "price_monthly_cents" in plan
            assert "has_notifications" in plan
            assert "has_analytics_export" in plan

    @pytest.mark.asyncio
    async def test_free_plan_limits(self, client: AsyncClient):
        """Free plan has correct limits."""
        response = await client.get("/api/v1/billing/plans")
        plans = response.json()["plans"]
        free = next(p for p in plans if p["name"] == "free")
        assert free["max_properties"] == 1
        assert free["max_ai_queries_per_month"] == 50
        assert free["has_notifications"] is False
        assert free["price_monthly_cents"] == 0


class TestGetSubscription:
    """Test GET /api/v1/billing/subscription."""

    @pytest.mark.asyncio
    async def test_get_subscription_success(
        self, db_session: AsyncSession, client: AsyncClient
    ):
        """Returns current subscription with usage stats."""
        _, headers = await _create_user_with_plan(db_session, "pro")
        response = await client.get("/api/v1/billing/subscription", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["plan"]["name"] == "pro"
        assert data["status"] == "active"
        assert "usage" in data
        assert data["usage"]["ai_queries_used"] == 0
        assert data["usage"]["properties_used"] == 0

    @pytest.mark.asyncio
    async def test_get_subscription_no_auth(self, client: AsyncClient):
        """Should return 401 without auth."""
        response = await client.get("/api/v1/billing/subscription")
        assert response.status_code == 401


class TestCheckout:
    """Test POST /api/v1/billing/checkout."""

    @pytest.mark.asyncio
    async def test_checkout_pro(
        self, db_session: AsyncSession, client: AsyncClient
    ):
        """Create checkout session for pro plan."""
        _, headers = await _create_user_with_plan(db_session, "free")

        mock_session = MagicMock()
        mock_session.url = "https://checkout.stripe.com/test_session"
        mock_session.id = "cs_test_123"

        with (
            patch(
                "app.api.v1.billing.ensure_stripe_customer",
                new_callable=AsyncMock,
                return_value="cus_test_123",
            ),
            patch(
                "app.api.v1.billing.create_checkout_session",
                new_callable=AsyncMock,
                return_value=mock_session,
            ),
        ):
            response = await client.post(
                "/api/v1/billing/checkout",
                json={"plan": "pro"},
                headers=headers,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["checkout_url"] == "https://checkout.stripe.com/test_session"
        assert data["session_id"] == "cs_test_123"

    @pytest.mark.asyncio
    async def test_checkout_business(
        self, db_session: AsyncSession, client: AsyncClient
    ):
        """Create checkout session for business plan."""
        _, headers = await _create_user_with_plan(db_session, "free")

        mock_session = MagicMock()
        mock_session.url = "https://checkout.stripe.com/biz_session"
        mock_session.id = "cs_test_biz"

        with (
            patch(
                "app.api.v1.billing.ensure_stripe_customer",
                new_callable=AsyncMock,
                return_value="cus_test_biz",
            ),
            patch(
                "app.api.v1.billing.create_checkout_session",
                new_callable=AsyncMock,
                return_value=mock_session,
            ),
        ):
            response = await client.post(
                "/api/v1/billing/checkout",
                json={"plan": "business"},
                headers=headers,
            )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_checkout_invalid_plan(
        self, db_session: AsyncSession, client: AsyncClient
    ):
        """Invalid plan name returns 400."""
        _, headers = await _create_user_with_plan(db_session, "free")
        response = await client.post(
            "/api/v1/billing/checkout",
            json={"plan": "premium"},
            headers=headers,
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_checkout_free_plan_rejected(
        self, db_session: AsyncSession, client: AsyncClient
    ):
        """Cannot checkout to free plan."""
        _, headers = await _create_user_with_plan(db_session, "free")
        response = await client.post(
            "/api/v1/billing/checkout",
            json={"plan": "free"},
            headers=headers,
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_checkout_no_auth(self, client: AsyncClient):
        """Checkout requires auth."""
        response = await client.post(
            "/api/v1/billing/checkout",
            json={"plan": "pro"},
        )
        assert response.status_code == 401


class TestPortal:
    """Test POST /api/v1/billing/portal."""

    @pytest.mark.asyncio
    async def test_portal_no_stripe_customer(
        self, db_session: AsyncSession, client: AsyncClient
    ):
        """User without Stripe customer ID gets 400."""
        _, headers = await _create_user_with_plan(db_session, "free")
        response = await client.post(
            "/api/v1/billing/portal",
            json={},
            headers=headers,
        )
        assert response.status_code == 400
        assert "No Stripe customer" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_portal_success(
        self, db_session: AsyncSession, client: AsyncClient
    ):
        """User with Stripe customer can access portal."""
        _, headers = await _create_user_with_plan(
            db_session, "pro", stripe_customer_id="cus_portal_123"
        )

        mock_session = MagicMock()
        mock_session.url = "https://billing.stripe.com/portal_session"

        with patch(
            "app.api.v1.billing.create_portal_session",
            new_callable=AsyncMock,
            return_value=mock_session,
        ):
            response = await client.post(
                "/api/v1/billing/portal",
                json={},
                headers=headers,
            )

        assert response.status_code == 200
        assert response.json()["portal_url"] == "https://billing.stripe.com/portal_session"

    @pytest.mark.asyncio
    async def test_portal_no_auth(self, client: AsyncClient):
        """Portal requires auth."""
        response = await client.post(
            "/api/v1/billing/portal",
            json={},
        )
        assert response.status_code == 401
