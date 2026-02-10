"""Tests for MCP tool functions — called directly (not through MCP protocol).

Uses the test database (villa_ops_test). The MCP session factory is overridden
to return the same db_session used by conftest fixtures, so tool functions see
test data within the same transaction (which rolls back after each test).
"""

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.mcp import set_session_factory
from app.models.booking import Booking
from app.models.guest import Guest
from app.models.property import Property
from app.models.user import User

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# MCP session factory setup — share the test db_session with MCP tools
# ---------------------------------------------------------------------------


class _TestSessionContext:
    """Async context manager that yields the shared test session."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def __aenter__(self) -> AsyncSession:
        return self._session

    async def __aexit__(self, *args):
        # Don't close — the conftest fixture handles lifecycle
        pass


class _TestSessionFactory:
    """Callable that returns a context manager wrapping the shared session."""

    def __init__(self, session: AsyncSession):
        self._session = session

    def __call__(self) -> _TestSessionContext:
        return _TestSessionContext(self._session)


@pytest.fixture(autouse=True)
def setup_mcp_session(db_session: AsyncSession, setup_test_db):
    """Override MCP session factory to share the test db_session."""
    set_session_factory(_TestSessionFactory(db_session))
    yield


# ---------------------------------------------------------------------------
# Test data fixtures — insert directly via ORM
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def mcp_owner(db_session: AsyncSession) -> User:
    """Create a property owner for MCP tool tests."""
    from app.auth.passwords import hash_password

    user = User(
        email=f"mcp-owner-{uuid.uuid4().hex[:8]}@test.com",
        hashed_password=hash_password("testpass"),
        name="MCP Test Owner",
        auth_provider="local",
        is_active=True,
        role="manager",
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest_asyncio.fixture
async def mcp_property(db_session: AsyncSession, mcp_owner: User) -> Property:
    """Create a test property for MCP tool tests."""
    prop = Property(
        owner_id=mcp_owner.id,
        name="MCP Test Villa Canggu",
        property_type="villa",
        location="Canggu, Bali",
        max_guests=8,
        base_price_per_night=Decimal("200.00"),
        status="active",
    )
    db_session.add(prop)
    await db_session.flush()
    return prop


@pytest_asyncio.fixture
async def mcp_guest(db_session: AsyncSession) -> Guest:
    """Create a test guest for MCP tool tests."""
    guest = Guest(
        name="Sarah Chen",
        email=f"sarah-{uuid.uuid4().hex[:8]}@test.com",
        phone="+61400111222",
        nationality="Australian",
    )
    db_session.add(guest)
    await db_session.flush()
    return guest


@pytest_asyncio.fixture
async def mcp_bookings(
    db_session: AsyncSession,
    mcp_property: Property,
    mcp_guest: Guest,
) -> list[Booking]:
    """Create test bookings spanning various dates and statuses."""
    today = date.today()
    bookings = [
        Booking(
            property_id=mcp_property.id,
            guest_id=mcp_guest.id,
            check_in=today - timedelta(days=20),
            check_out=today - timedelta(days=15),
            num_guests=2,
            status="checked_out",
            total_price=Decimal("1000.00"),
        ),
        Booking(
            property_id=mcp_property.id,
            guest_id=mcp_guest.id,
            check_in=today - timedelta(days=10),
            check_out=today - timedelta(days=5),
            num_guests=3,
            status="confirmed",
            total_price=Decimal("1500.00"),
        ),
        Booking(
            property_id=mcp_property.id,
            guest_id=mcp_guest.id,
            check_in=today + timedelta(days=5),
            check_out=today + timedelta(days=10),
            num_guests=2,
            status="pending",
            total_price=Decimal("800.00"),
        ),
    ]
    for b in bookings:
        db_session.add(b)
    await db_session.flush()
    return bookings


# ---------------------------------------------------------------------------
# booking_search tests
# ---------------------------------------------------------------------------


class TestBookingSearch:
    async def test_search_no_filters(self, mcp_bookings):
        from app.mcp.tools.booking_tools import booking_search

        result = await booking_search()
        assert "bookings" in result
        assert "total" in result
        assert result["total"] >= len(mcp_bookings)

    async def test_search_by_status(self, mcp_bookings):
        from app.mcp.tools.booking_tools import booking_search

        result = await booking_search(status="confirmed")
        assert "bookings" in result
        for b in result["bookings"]:
            assert b["status"] == "confirmed"


# ---------------------------------------------------------------------------
# booking_analytics tests
# ---------------------------------------------------------------------------


class TestBookingAnalytics:
    async def test_summary(self, mcp_property, mcp_bookings):
        from app.mcp.tools.analytics_tools import booking_analytics

        today = date.today()
        result = await booking_analytics(
            property_id=str(mcp_property.id),
            period_start=(today - timedelta(days=30)).isoformat(),
            period_end=(today + timedelta(days=15)).isoformat(),
            metric="summary",
        )
        assert "error" not in result
        assert "occupancy" in result
        assert "revenue" in result
        assert "trends" in result
        assert result["properties_analyzed"] == 1
        assert int(result["occupancy"]["booked_days"]) > 0
        assert Decimal(result["revenue"]["total_revenue"]) > 0

    async def test_with_property_filter(self, mcp_property, mcp_bookings):
        from app.mcp.tools.analytics_tools import booking_analytics

        result = await booking_analytics(
            property_name="MCP Test Villa",
            metric="occupancy",
        )
        assert "error" not in result
        assert "occupancy" in result
        assert len(result["occupancy"]["per_property"]) >= 1
        prop_names = [p["name"] for p in result["occupancy"]["per_property"]]
        assert mcp_property.name in prop_names

    async def test_empty_date_range(self, mcp_property, mcp_bookings):
        from app.mcp.tools.analytics_tools import booking_analytics

        # A far-future range with no bookings
        result = await booking_analytics(
            property_id=str(mcp_property.id),
            period_start="2099-01-01",
            period_end="2099-01-31",
            metric="summary",
        )
        assert "error" not in result
        assert result["occupancy"]["booked_days"] == 0
        assert result["revenue"]["booking_count"] == 0

    async def test_invalid_metric(self):
        from app.mcp.tools.analytics_tools import booking_analytics

        result = await booking_analytics(metric="invalid")
        assert "error" in result
        assert "Invalid metric" in result["error"]

    async def test_invalid_dates(self):
        from app.mcp.tools.analytics_tools import booking_analytics

        result = await booking_analytics(period_start="2026-01-31", period_end="2026-01-01")
        assert "error" in result
        assert "period_end must be after" in result["error"]


# ---------------------------------------------------------------------------
# guest_lookup tests
# ---------------------------------------------------------------------------


class TestGuestLookup:
    async def test_lookup_by_name(self, mcp_guest):
        from app.mcp.tools.guest_tools import guest_lookup

        result = await guest_lookup(name="Sarah")
        assert "guests" in result
        assert result["total"] >= 1
        names = [g["name"] for g in result["guests"]]
        assert any("Sarah" in n for n in names)


# ---------------------------------------------------------------------------
# property_manage tests
# ---------------------------------------------------------------------------


class TestPropertyManage:
    async def test_check_availability_available(self, mcp_property, mcp_bookings):
        from app.mcp.tools.property_tools import property_manage

        today = date.today()
        # Pick a date range with no bookings
        result = await property_manage(
            action="check_availability",
            property_id=str(mcp_property.id),
            check_in=(today + timedelta(days=30)).isoformat(),
            check_out=(today + timedelta(days=35)).isoformat(),
        )
        assert result["available"] is True

    async def test_check_availability_conflict(self, mcp_property, mcp_bookings):
        from app.mcp.tools.property_tools import property_manage

        today = date.today()
        # Use dates that overlap with the pending booking (today+5 to today+10)
        result = await property_manage(
            action="check_availability",
            property_id=str(mcp_property.id),
            check_in=(today + timedelta(days=6)).isoformat(),
            check_out=(today + timedelta(days=8)).isoformat(),
        )
        assert result["available"] is False
        assert len(result["conflicts"]) > 0


# ---------------------------------------------------------------------------
# send_notification tests
# ---------------------------------------------------------------------------


class TestSendNotification:
    async def test_valid_template_with_booking(self, mcp_guest, mcp_bookings):
        from app.mcp.tools.notification_tools import send_notification

        booking = mcp_bookings[1]  # confirmed booking
        result = await send_notification(
            template="booking_confirmation",
            guest_id=str(mcp_guest.id),
            booking_id=str(booking.id),
        )
        assert result["status"] == "simulated"
        assert result["notification"]["recipient_name"] == "Sarah Chen"
        assert "Confirmed" in result["notification"]["subject"]
        assert result["notification"]["template_used"] == "booking_confirmation"

    async def test_check_in_reminder(self, mcp_guest, mcp_bookings):
        from app.mcp.tools.notification_tools import send_notification

        booking = mcp_bookings[2]  # pending booking
        result = await send_notification(
            template="check_in_reminder",
            guest_id=str(mcp_guest.id),
            booking_id=str(booking.id),
        )
        assert result["status"] == "simulated"
        assert "Check-in" in result["notification"]["subject"]

    async def test_custom_template(self, mcp_guest):
        from app.mcp.tools.notification_tools import send_notification

        result = await send_notification(
            template="custom",
            guest_id=str(mcp_guest.id),
            custom_message="Hello! Just checking in on your plans.",
        )
        assert result["status"] == "simulated"
        assert "checking in" in result["notification"]["body"]

    async def test_invalid_template(self, mcp_guest):
        from app.mcp.tools.notification_tools import send_notification

        result = await send_notification(
            template="nonexistent",
            guest_id=str(mcp_guest.id),
        )
        assert result["status"] == "failed"
        assert "Invalid template" in result["error"]

    async def test_missing_guest_info(self):
        from app.mcp.tools.notification_tools import send_notification

        result = await send_notification(template="welcome")
        assert result["status"] == "failed"
        assert "guest_id or guest_email" in result["error"]

    async def test_custom_without_message(self, mcp_guest):
        from app.mcp.tools.notification_tools import send_notification

        result = await send_notification(
            template="custom",
            guest_id=str(mcp_guest.id),
        )
        assert result["status"] == "failed"
        assert "custom_message is required" in result["error"]

    async def test_guest_not_found(self):
        from app.mcp.tools.notification_tools import send_notification

        result = await send_notification(
            template="welcome",
            guest_id=str(uuid.uuid4()),
        )
        assert result["status"] == "failed"
        assert "Guest not found" in result["error"]

    async def test_lookup_by_email(self, mcp_guest):
        from app.mcp.tools.notification_tools import send_notification

        result = await send_notification(
            template="welcome",
            guest_email=mcp_guest.email,
        )
        assert result["status"] == "simulated"
        assert result["notification"]["recipient_email"] == mcp_guest.email
