"""Tests for analytics endpoints — occupancy rates."""

import uuid
from datetime import date, timedelta

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _date_str(offset: int) -> str:
    """Return an ISO date string relative to today."""
    return (date.today() + timedelta(days=offset)).isoformat()


# ---------------------------------------------------------------------------
# GET /api/v1/analytics/occupancy
# ---------------------------------------------------------------------------


class TestOccupancy:
    """Tests for the occupancy analytics endpoint."""

    async def test_occupancy_with_bookings(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_property: dict,
        test_guest: dict,
    ) -> None:
        """Occupancy should reflect booked days within the requested period."""
        # Create a confirmed booking: 5 nights starting 10 days ago
        ci = _date_str(-10)
        co = _date_str(-5)
        create_resp = await client.post(
            "/api/v1/bookings",
            json={
                "property_id": test_property["id"],
                "guest_id": test_guest["id"],
                "check_in": ci,
                "check_out": co,
                "num_guests": 2,
                "status": "confirmed",
            },
            headers=auth_headers,
        )
        assert create_resp.status_code == 201

        # Query occupancy for a 30-day window that includes the booking
        period_start = _date_str(-15)
        period_end = _date_str(15)
        response = await client.get(
            "/api/v1/analytics/occupancy",
            params={"period_start": period_start, "period_end": period_end},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()

        assert data["period_start"] == period_start
        assert data["period_end"] == period_end
        assert "properties" in data
        assert "overall_occupancy_rate" in data
        assert len(data["properties"]) >= 1

        # Find our test property in the results
        prop_stats = next(
            (p for p in data["properties"] if p["property_id"] == test_property["id"]),
            None,
        )
        assert prop_stats is not None
        assert prop_stats["property_name"] == test_property["name"]
        assert prop_stats["total_days"] == 30
        assert prop_stats["booked_days"] == 5
        assert float(prop_stats["occupancy_rate"]) > 0

        # Overall rate should also be > 0
        assert float(data["overall_occupancy_rate"]) > 0

    async def test_occupancy_no_bookings(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_property: dict,
    ) -> None:
        """A property with no bookings should have 0% occupancy."""
        # Use a far-future period where there are definitely no bookings
        period_start = _date_str(500)
        period_end = _date_str(530)
        response = await client.get(
            "/api/v1/analytics/occupancy",
            params={"period_start": period_start, "period_end": period_end},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()

        prop_stats = next(
            (p for p in data["properties"] if p["property_id"] == test_property["id"]),
            None,
        )
        assert prop_stats is not None
        assert prop_stats["booked_days"] == 0
        assert float(prop_stats["occupancy_rate"]) == 0.0

    async def test_occupancy_invalid_period(
        self,
        client: AsyncClient,
        auth_headers: dict,
    ) -> None:
        """period_end must be after period_start."""
        response = await client.get(
            "/api/v1/analytics/occupancy",
            params={
                "period_start": _date_str(10),
                "period_end": _date_str(5),  # before start
            },
            headers=auth_headers,
        )
        assert response.status_code == 400
        assert "period_end" in response.json()["detail"].lower()

    async def test_occupancy_same_dates(
        self,
        client: AsyncClient,
        auth_headers: dict,
    ) -> None:
        """period_end equal to period_start is invalid (zero-length period)."""
        same_date = _date_str(20)
        response = await client.get(
            "/api/v1/analytics/occupancy",
            params={"period_start": same_date, "period_end": same_date},
            headers=auth_headers,
        )
        assert response.status_code == 400

    async def test_occupancy_filter_by_property(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_property: dict,
        test_guest: dict,
    ) -> None:
        """Filtering by property_id should return only that property's stats."""
        # Create a second property
        second_prop_resp = await client.post(
            "/api/v1/properties",
            json={
                "name": "Analytics Villa 2",
                "property_type": "villa",
                "location": "Canggu, Bali",
            },
            headers=auth_headers,
        )
        assert second_prop_resp.status_code == 201
        second_prop_resp.json()

        # Create a booking on the first property
        ci = _date_str(-8)
        co = _date_str(-3)
        await client.post(
            "/api/v1/bookings",
            json={
                "property_id": test_property["id"],
                "guest_id": test_guest["id"],
                "check_in": ci,
                "check_out": co,
                "num_guests": 1,
                "status": "confirmed",
            },
            headers=auth_headers,
        )

        # Query occupancy filtered to the first property only
        period_start = _date_str(-15)
        period_end = _date_str(15)
        response = await client.get(
            "/api/v1/analytics/occupancy",
            params={
                "period_start": period_start,
                "period_end": period_end,
                "property_id": test_property["id"],
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()

        # Should only contain the filtered property
        assert len(data["properties"]) == 1
        assert data["properties"][0]["property_id"] == test_property["id"]

    async def test_occupancy_filter_nonexistent_property(
        self,
        client: AsyncClient,
        auth_headers: dict,
    ) -> None:
        """Filtering by a non-existent property_id should return 404."""
        fake_id = str(uuid.uuid4())
        response = await client.get(
            "/api/v1/analytics/occupancy",
            params={
                "period_start": _date_str(-10),
                "period_end": _date_str(10),
                "property_id": fake_id,
            },
            headers=auth_headers,
        )
        assert response.status_code == 404

    async def test_occupancy_cancelled_bookings_excluded(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_property: dict,
        test_guest: dict,
    ) -> None:
        """Cancelled bookings should not count towards occupancy."""
        # Create a cancelled booking in a unique date range
        ci = _date_str(400)
        co = _date_str(405)
        await client.post(
            "/api/v1/bookings",
            json={
                "property_id": test_property["id"],
                "guest_id": test_guest["id"],
                "check_in": ci,
                "check_out": co,
                "num_guests": 1,
                "status": "pending",
            },
            headers=auth_headers,
        )

        # Update it to cancelled
        bookings_resp = await client.get(
            "/api/v1/bookings",
            params={"property_id": test_property["id"]},
            headers=auth_headers,
        )
        assert bookings_resp.status_code == 200
        matching = [b for b in bookings_resp.json()["items"] if b["check_in"] == ci]
        assert len(matching) >= 1
        booking_id = matching[0]["id"]

        cancel_resp = await client.put(
            f"/api/v1/bookings/{booking_id}",
            json={"status": "cancelled"},
            headers=auth_headers,
        )
        assert cancel_resp.status_code == 200

        # Check occupancy — cancelled booking should not contribute
        period_start = _date_str(395)
        period_end = _date_str(410)
        response = await client.get(
            "/api/v1/analytics/occupancy",
            params={
                "period_start": period_start,
                "period_end": period_end,
                "property_id": test_property["id"],
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["properties"]) == 1
        assert data["properties"][0]["booked_days"] == 0
        assert float(data["properties"][0]["occupancy_rate"]) == 0.0

    async def test_occupancy_missing_params(
        self,
        client: AsyncClient,
        auth_headers: dict,
    ) -> None:
        """Missing required query parameters should return 422."""
        # Missing period_end
        response = await client.get(
            "/api/v1/analytics/occupancy",
            params={"period_start": _date_str(0)},
            headers=auth_headers,
        )
        assert response.status_code == 422

        # Missing period_start
        response = await client.get(
            "/api/v1/analytics/occupancy",
            params={"period_end": _date_str(10)},
            headers=auth_headers,
        )
        assert response.status_code == 422

        # Missing both
        response = await client.get(
            "/api/v1/analytics/occupancy",
            headers=auth_headers,
        )
        assert response.status_code == 422

    async def test_occupancy_unauthenticated(self, client: AsyncClient) -> None:
        response = await client.get(
            "/api/v1/analytics/occupancy",
            params={
                "period_start": _date_str(-10),
                "period_end": _date_str(10),
            },
        )
        assert response.status_code in (401, 403)

    async def test_occupancy_multiple_bookings_same_property(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_property: dict,
        test_guest: dict,
    ) -> None:
        """Multiple non-overlapping bookings should sum their booked days."""
        # Booking 1: 3 nights
        ci1 = _date_str(450)
        co1 = _date_str(453)
        await client.post(
            "/api/v1/bookings",
            json={
                "property_id": test_property["id"],
                "guest_id": test_guest["id"],
                "check_in": ci1,
                "check_out": co1,
                "num_guests": 1,
                "status": "confirmed",
            },
            headers=auth_headers,
        )

        # Booking 2: 4 nights (non-overlapping)
        ci2 = _date_str(460)
        co2 = _date_str(464)
        await client.post(
            "/api/v1/bookings",
            json={
                "property_id": test_property["id"],
                "guest_id": test_guest["id"],
                "check_in": ci2,
                "check_out": co2,
                "num_guests": 1,
                "status": "confirmed",
            },
            headers=auth_headers,
        )

        # Query a period covering both bookings
        period_start = _date_str(445)
        period_end = _date_str(470)
        response = await client.get(
            "/api/v1/analytics/occupancy",
            params={
                "period_start": period_start,
                "period_end": period_end,
                "property_id": test_property["id"],
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["properties"]) == 1

        prop_stats = data["properties"][0]
        assert prop_stats["total_days"] == 25
        assert prop_stats["booked_days"] == 7  # 3 + 4
        # Occupancy should be 7/25 = 28%
        assert float(prop_stats["occupancy_rate"]) == pytest.approx(28.00, abs=0.01)
