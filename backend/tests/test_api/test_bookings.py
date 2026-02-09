"""Tests for booking CRUD endpoints."""

import uuid
from datetime import date, timedelta

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _future_dates(offset_start: int = 30, nights: int = 5) -> tuple[str, str]:
    """Return a (check_in, check_out) pair safely in the future as ISO strings."""
    check_in = date.today() + timedelta(days=offset_start)
    check_out = check_in + timedelta(days=nights)
    return check_in.isoformat(), check_out.isoformat()


# ---------------------------------------------------------------------------
# POST /api/v1/bookings
# ---------------------------------------------------------------------------


class TestCreateBooking:
    """Tests for creating bookings."""

    async def test_create_success(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_property: dict,
        test_guest: dict,
    ) -> None:
        ci, co = _future_dates(30, 5)
        response = await client.post(
            "/api/v1/bookings",
            json={
                "property_id": test_property["id"],
                "guest_id": test_guest["id"],
                "check_in": ci,
                "check_out": co,
                "num_guests": 2,
                "status": "confirmed",
                "total_price": 750.00,
                "special_requests": "Late check-in around 10pm",
            },
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["property_id"] == test_property["id"]
        assert data["guest_id"] == test_guest["id"]
        assert data["check_in"] == ci
        assert data["check_out"] == co
        assert data["num_guests"] == 2
        assert data["status"] == "confirmed"
        assert float(data["total_price"]) == 750.00
        assert data["special_requests"] == "Late check-in around 10pm"
        assert "id" in data
        assert "created_at" in data

    async def test_create_minimal(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_property: dict,
        test_guest: dict,
    ) -> None:
        """Only required fields — defaults to status='pending', num_guests=1."""
        ci, co = _future_dates(40, 3)
        response = await client.post(
            "/api/v1/bookings",
            json={
                "property_id": test_property["id"],
                "guest_id": test_guest["id"],
                "check_in": ci,
                "check_out": co,
            },
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "pending"
        assert data["num_guests"] == 1

    async def test_create_date_conflict(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_property: dict,
        test_guest: dict,
    ) -> None:
        """Overlapping non-cancelled bookings on the same property should be rejected."""
        ci, co = _future_dates(50, 5)
        payload = {
            "property_id": test_property["id"],
            "guest_id": test_guest["id"],
            "check_in": ci,
            "check_out": co,
            "num_guests": 2,
        }

        resp1 = await client.post("/api/v1/bookings", json=payload, headers=auth_headers)
        assert resp1.status_code == 201

        # Overlapping booking (same dates)
        resp2 = await client.post("/api/v1/bookings", json=payload, headers=auth_headers)
        assert resp2.status_code == 409
        assert "conflict" in resp2.json()["detail"].lower()

    async def test_create_partial_overlap_conflict(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_property: dict,
        test_guest: dict,
    ) -> None:
        """Partially overlapping dates should also conflict."""
        ci1 = (date.today() + timedelta(days=60)).isoformat()
        co1 = (date.today() + timedelta(days=65)).isoformat()

        await client.post(
            "/api/v1/bookings",
            json={
                "property_id": test_property["id"],
                "guest_id": test_guest["id"],
                "check_in": ci1,
                "check_out": co1,
                "num_guests": 1,
            },
            headers=auth_headers,
        )

        # Overlap: starts 2 days before the first booking ends
        ci2 = (date.today() + timedelta(days=63)).isoformat()
        co2 = (date.today() + timedelta(days=68)).isoformat()

        resp = await client.post(
            "/api/v1/bookings",
            json={
                "property_id": test_property["id"],
                "guest_id": test_guest["id"],
                "check_in": ci2,
                "check_out": co2,
                "num_guests": 1,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 409

    async def test_create_invalid_dates(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_property: dict,
        test_guest: dict,
    ) -> None:
        """check_out must be after check_in."""
        ci = (date.today() + timedelta(days=70)).isoformat()
        co = ci  # same day — invalid
        response = await client.post(
            "/api/v1/bookings",
            json={
                "property_id": test_property["id"],
                "guest_id": test_guest["id"],
                "check_in": ci,
                "check_out": co,
                "num_guests": 1,
            },
            headers=auth_headers,
        )
        assert response.status_code == 422

    async def test_create_checkout_before_checkin(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_property: dict,
        test_guest: dict,
    ) -> None:
        ci = (date.today() + timedelta(days=80)).isoformat()
        co = (date.today() + timedelta(days=78)).isoformat()
        response = await client.post(
            "/api/v1/bookings",
            json={
                "property_id": test_property["id"],
                "guest_id": test_guest["id"],
                "check_in": ci,
                "check_out": co,
                "num_guests": 1,
            },
            headers=auth_headers,
        )
        assert response.status_code == 422

    async def test_create_nonexistent_property(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_guest: dict,
    ) -> None:
        ci, co = _future_dates(90, 3)
        fake_id = str(uuid.uuid4())
        response = await client.post(
            "/api/v1/bookings",
            json={
                "property_id": fake_id,
                "guest_id": test_guest["id"],
                "check_in": ci,
                "check_out": co,
            },
            headers=auth_headers,
        )
        assert response.status_code == 404
        assert "property" in response.json()["detail"].lower()

    async def test_create_nonexistent_guest(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_property: dict,
    ) -> None:
        ci, co = _future_dates(100, 3)
        fake_id = str(uuid.uuid4())
        response = await client.post(
            "/api/v1/bookings",
            json={
                "property_id": test_property["id"],
                "guest_id": fake_id,
                "check_in": ci,
                "check_out": co,
            },
            headers=auth_headers,
        )
        assert response.status_code == 404
        assert "guest" in response.json()["detail"].lower()

    async def test_create_other_users_property(
        self,
        client: AsyncClient,
        test_property: dict,
        test_guest: dict,
        db_session,
    ) -> None:
        """Booking on another user's property should fail with 404."""
        from app.auth.jwt import create_token_pair
        from app.auth.passwords import hash_password
        from app.models.user import User

        other_user = User(
            email=f"booking-other-{uuid.uuid4().hex[:8]}@test.com",
            hashed_password=hash_password("otherpass1"),
            name="Other Owner",
            auth_provider="local",
            is_active=True,
            role="manager",
        )
        db_session.add(other_user)
        await db_session.flush()

        tokens = create_token_pair(str(other_user.id))
        other_headers = {"Authorization": f"Bearer {tokens['access_token']}"}

        ci, co = _future_dates(110, 3)
        response = await client.post(
            "/api/v1/bookings",
            json={
                "property_id": test_property["id"],
                "guest_id": test_guest["id"],
                "check_in": ci,
                "check_out": co,
            },
            headers=other_headers,
        )
        assert response.status_code == 404

    async def test_create_unauthenticated(
        self,
        client: AsyncClient,
        test_property: dict,
        test_guest: dict,
    ) -> None:
        ci, co = _future_dates(120, 3)
        response = await client.post(
            "/api/v1/bookings",
            json={
                "property_id": test_property["id"],
                "guest_id": test_guest["id"],
                "check_in": ci,
                "check_out": co,
            },
        )
        assert response.status_code in (401, 403)


# ---------------------------------------------------------------------------
# GET /api/v1/bookings
# ---------------------------------------------------------------------------


class TestListBookings:
    """Tests for listing bookings."""

    async def test_list_own_bookings_only(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_property: dict,
        test_guest: dict,
    ) -> None:
        ci, co = _future_dates(130, 3)
        await client.post(
            "/api/v1/bookings",
            json={
                "property_id": test_property["id"],
                "guest_id": test_guest["id"],
                "check_in": ci,
                "check_out": co,
            },
            headers=auth_headers,
        )

        response = await client.get("/api/v1/bookings", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert data["total"] >= 1
        assert all("id" in item for item in data["items"])

    async def test_list_filter_by_status(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_property: dict,
        test_guest: dict,
    ) -> None:
        ci, co = _future_dates(140, 3)
        await client.post(
            "/api/v1/bookings",
            json={
                "property_id": test_property["id"],
                "guest_id": test_guest["id"],
                "check_in": ci,
                "check_out": co,
                "status": "confirmed",
            },
            headers=auth_headers,
        )

        response = await client.get(
            "/api/v1/bookings",
            params={"status": "confirmed"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert all(item["status"] == "confirmed" for item in data["items"])

    async def test_list_filter_by_property(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_property: dict,
        test_guest: dict,
    ) -> None:
        ci, co = _future_dates(150, 3)
        await client.post(
            "/api/v1/bookings",
            json={
                "property_id": test_property["id"],
                "guest_id": test_guest["id"],
                "check_in": ci,
                "check_out": co,
            },
            headers=auth_headers,
        )

        response = await client.get(
            "/api/v1/bookings",
            params={"property_id": test_property["id"]},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert all(item["property_id"] == test_property["id"] for item in data["items"])

    async def test_list_filter_by_date_range(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_property: dict,
        test_guest: dict,
    ) -> None:
        ci_date = date.today() + timedelta(days=160)
        co_date = ci_date + timedelta(days=5)
        ci = ci_date.isoformat()
        co = co_date.isoformat()

        await client.post(
            "/api/v1/bookings",
            json={
                "property_id": test_property["id"],
                "guest_id": test_guest["id"],
                "check_in": ci,
                "check_out": co,
            },
            headers=auth_headers,
        )

        response = await client.get(
            "/api/v1/bookings",
            params={
                "check_in_from": ci,
                "check_in_to": (ci_date + timedelta(days=1)).isoformat(),
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1

    async def test_list_pagination(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_property: dict,
        test_guest: dict,
    ) -> None:
        # Create a couple of bookings
        for offset in (170, 180):
            ci, co = _future_dates(offset, 3)
            await client.post(
                "/api/v1/bookings",
                json={
                    "property_id": test_property["id"],
                    "guest_id": test_guest["id"],
                    "check_in": ci,
                    "check_out": co,
                },
                headers=auth_headers,
            )

        response = await client.get(
            "/api/v1/bookings",
            params={"skip": 0, "limit": 1},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) <= 1

    async def test_list_unauthenticated(self, client: AsyncClient) -> None:
        response = await client.get("/api/v1/bookings")
        assert response.status_code in (401, 403)


# ---------------------------------------------------------------------------
# GET /api/v1/bookings/{booking_id}
# ---------------------------------------------------------------------------


class TestGetBooking:
    """Tests for getting a single booking with detail."""

    async def test_get_detail_includes_property_and_guest(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_property: dict,
        test_guest: dict,
    ) -> None:
        ci, co = _future_dates(190, 4)
        create_resp = await client.post(
            "/api/v1/bookings",
            json={
                "property_id": test_property["id"],
                "guest_id": test_guest["id"],
                "check_in": ci,
                "check_out": co,
                "num_guests": 2,
            },
            headers=auth_headers,
        )
        assert create_resp.status_code == 201
        booking_id = create_resp.json()["id"]

        response = await client.get(f"/api/v1/bookings/{booking_id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == booking_id
        assert data["property"] is not None
        assert data["property"]["id"] == test_property["id"]
        assert data["guest"] is not None
        assert data["guest"]["id"] == test_guest["id"]

    async def test_get_not_found(self, client: AsyncClient, auth_headers: dict) -> None:
        fake_id = str(uuid.uuid4())
        response = await client.get(f"/api/v1/bookings/{fake_id}", headers=auth_headers)
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# PUT /api/v1/bookings/{booking_id}
# ---------------------------------------------------------------------------


class TestUpdateBooking:
    """Tests for updating a booking."""

    async def _create_booking(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_property: dict,
        test_guest: dict,
        offset: int,
    ) -> dict:
        ci, co = _future_dates(offset, 5)
        resp = await client.post(
            "/api/v1/bookings",
            json={
                "property_id": test_property["id"],
                "guest_id": test_guest["id"],
                "check_in": ci,
                "check_out": co,
                "num_guests": 2,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 201
        return resp.json()

    async def test_update_status(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_property: dict,
        test_guest: dict,
    ) -> None:
        booking = await self._create_booking(client, auth_headers, test_property, test_guest, 200)
        response = await client.put(
            f"/api/v1/bookings/{booking['id']}",
            json={"status": "confirmed"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["status"] == "confirmed"

    async def test_update_special_requests(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_property: dict,
        test_guest: dict,
    ) -> None:
        booking = await self._create_booking(client, auth_headers, test_property, test_guest, 210)
        response = await client.put(
            f"/api/v1/bookings/{booking['id']}",
            json={"special_requests": "Extra towels please"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["special_requests"] == "Extra towels please"

    async def test_update_dates_no_conflict(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_property: dict,
        test_guest: dict,
    ) -> None:
        booking = await self._create_booking(client, auth_headers, test_property, test_guest, 220)
        new_ci = (date.today() + timedelta(days=225)).isoformat()
        new_co = (date.today() + timedelta(days=228)).isoformat()
        response = await client.put(
            f"/api/v1/bookings/{booking['id']}",
            json={"check_in": new_ci, "check_out": new_co},
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["check_in"] == new_ci
        assert response.json()["check_out"] == new_co

    async def test_update_dates_conflict(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_property: dict,
        test_guest: dict,
    ) -> None:
        """Changing dates to overlap with another booking should fail."""
        # Create first booking
        ci1 = (date.today() + timedelta(days=230)).isoformat()
        co1 = (date.today() + timedelta(days=235)).isoformat()
        await client.post(
            "/api/v1/bookings",
            json={
                "property_id": test_property["id"],
                "guest_id": test_guest["id"],
                "check_in": ci1,
                "check_out": co1,
            },
            headers=auth_headers,
        )

        # Create second booking (non-overlapping)
        booking2 = await self._create_booking(client, auth_headers, test_property, test_guest, 240)

        # Try to update second booking to overlap with first
        response = await client.put(
            f"/api/v1/bookings/{booking2['id']}",
            json={"check_in": ci1, "check_out": co1},
            headers=auth_headers,
        )
        assert response.status_code == 409

    async def test_update_not_found(self, client: AsyncClient, auth_headers: dict) -> None:
        fake_id = str(uuid.uuid4())
        response = await client.put(
            f"/api/v1/bookings/{fake_id}",
            json={"status": "confirmed"},
            headers=auth_headers,
        )
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /api/v1/bookings/{booking_id}
# ---------------------------------------------------------------------------


class TestDeleteBooking:
    """Tests for deleting a booking."""

    async def test_delete_success(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_property: dict,
        test_guest: dict,
    ) -> None:
        ci, co = _future_dates(250, 3)
        create_resp = await client.post(
            "/api/v1/bookings",
            json={
                "property_id": test_property["id"],
                "guest_id": test_guest["id"],
                "check_in": ci,
                "check_out": co,
            },
            headers=auth_headers,
        )
        assert create_resp.status_code == 201
        booking_id = create_resp.json()["id"]

        response = await client.delete(f"/api/v1/bookings/{booking_id}", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["message"] == "Booking deleted"

        # Verify it's gone
        get_resp = await client.get(f"/api/v1/bookings/{booking_id}", headers=auth_headers)
        assert get_resp.status_code == 404

    async def test_delete_not_found(self, client: AsyncClient, auth_headers: dict) -> None:
        fake_id = str(uuid.uuid4())
        response = await client.delete(f"/api/v1/bookings/{fake_id}", headers=auth_headers)
        assert response.status_code == 404
