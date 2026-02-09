"""Tests for guest CRUD endpoints."""

import uuid

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _unique_email() -> str:
    return f"guest-{uuid.uuid4().hex[:8]}@test.com"


# ---------------------------------------------------------------------------
# POST /api/v1/guests
# ---------------------------------------------------------------------------


class TestCreateGuest:
    """Tests for creating guests."""

    async def test_create_success(self, client: AsyncClient, auth_headers: dict) -> None:
        email = _unique_email()
        response = await client.post(
            "/api/v1/guests",
            json={
                "name": "Alice Walker",
                "email": email,
                "phone": "+61412345678",
                "nationality": "Australian",
                "notes": "Prefers quiet room",
            },
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Alice Walker"
        assert data["email"] == email
        assert data["phone"] == "+61412345678"
        assert data["nationality"] == "Australian"
        assert data["notes"] == "Prefers quiet room"
        assert "id" in data
        assert "created_at" in data

    async def test_create_minimal(self, client: AsyncClient, auth_headers: dict) -> None:
        """Only required fields: name and email."""
        email = _unique_email()
        response = await client.post(
            "/api/v1/guests",
            json={"name": "Minimal Guest", "email": email},
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Minimal Guest"
        assert data["email"] == email
        assert data["phone"] is None
        assert data["nationality"] is None
        assert data["notes"] is None

    async def test_create_duplicate_email(self, client: AsyncClient, auth_headers: dict) -> None:
        email = _unique_email()
        payload = {"name": "First Guest", "email": email}

        resp1 = await client.post("/api/v1/guests", json=payload, headers=auth_headers)
        assert resp1.status_code == 201

        resp2 = await client.post(
            "/api/v1/guests",
            json={"name": "Second Guest", "email": email},
            headers=auth_headers,
        )
        assert resp2.status_code == 409
        assert "already exists" in resp2.json()["detail"].lower()

    async def test_create_invalid_email(self, client: AsyncClient, auth_headers: dict) -> None:
        response = await client.post(
            "/api/v1/guests",
            json={"name": "Bad Email Guest", "email": "not-an-email"},
            headers=auth_headers,
        )
        assert response.status_code == 422

    async def test_create_missing_name(self, client: AsyncClient, auth_headers: dict) -> None:
        response = await client.post(
            "/api/v1/guests",
            json={"email": _unique_email()},
            headers=auth_headers,
        )
        assert response.status_code == 422

    async def test_create_missing_email(self, client: AsyncClient, auth_headers: dict) -> None:
        response = await client.post(
            "/api/v1/guests",
            json={"name": "No Email Guest"},
            headers=auth_headers,
        )
        assert response.status_code == 422

    async def test_create_unauthenticated(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/v1/guests",
            json={"name": "Unauth Guest", "email": _unique_email()},
        )
        assert response.status_code in (401, 403)


# ---------------------------------------------------------------------------
# GET /api/v1/guests
# ---------------------------------------------------------------------------


class TestListGuests:
    """Tests for listing / searching guests."""

    async def test_list_all(self, client: AsyncClient, auth_headers: dict) -> None:
        # Create a couple of guests
        for i in range(2):
            await client.post(
                "/api/v1/guests",
                json={"name": f"List Guest {i}", "email": _unique_email()},
                headers=auth_headers,
            )

        response = await client.get("/api/v1/guests", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert data["total"] >= 2
        assert all("id" in item for item in data["items"])

    async def test_search_by_name(self, client: AsyncClient, auth_headers: dict) -> None:
        unique_name = f"Searchable-{uuid.uuid4().hex[:6]}"
        await client.post(
            "/api/v1/guests",
            json={"name": unique_name, "email": _unique_email()},
            headers=auth_headers,
        )

        response = await client.get(
            "/api/v1/guests",
            params={"search": unique_name},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        assert any(unique_name in item["name"] for item in data["items"])

    async def test_search_by_email(self, client: AsyncClient, auth_headers: dict) -> None:
        email = _unique_email()
        await client.post(
            "/api/v1/guests",
            json={"name": "Email Search Guest", "email": email},
            headers=auth_headers,
        )

        # Search by partial email (the unique part)
        search_term = email.split("@")[0]
        response = await client.get(
            "/api/v1/guests",
            params={"search": search_term},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        assert any(email == item["email"] for item in data["items"])

    async def test_search_no_results(self, client: AsyncClient, auth_headers: dict) -> None:
        response = await client.get(
            "/api/v1/guests",
            params={"search": "zzz-nonexistent-guest-name-zzz"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["items"] == []

    async def test_list_pagination(self, client: AsyncClient, auth_headers: dict) -> None:
        for i in range(3):
            await client.post(
                "/api/v1/guests",
                json={"name": f"Page Guest {i}", "email": _unique_email()},
                headers=auth_headers,
            )

        response = await client.get(
            "/api/v1/guests",
            params={"skip": 0, "limit": 2},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) <= 2

    async def test_list_unauthenticated(self, client: AsyncClient) -> None:
        response = await client.get("/api/v1/guests")
        assert response.status_code in (401, 403)


# ---------------------------------------------------------------------------
# GET /api/v1/guests/{guest_id}
# ---------------------------------------------------------------------------


class TestGetGuest:
    """Tests for getting a single guest."""

    async def test_get_success(self, client: AsyncClient, auth_headers: dict, test_guest: dict) -> None:
        guest_id = test_guest["id"]
        response = await client.get(f"/api/v1/guests/{guest_id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == guest_id
        assert data["name"] == test_guest["name"]
        assert data["email"] == test_guest["email"]

    async def test_get_not_found(self, client: AsyncClient, auth_headers: dict) -> None:
        fake_id = str(uuid.uuid4())
        response = await client.get(f"/api/v1/guests/{fake_id}", headers=auth_headers)
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# PUT /api/v1/guests/{guest_id}
# ---------------------------------------------------------------------------


class TestUpdateGuest:
    """Tests for updating a guest."""

    async def test_update_name(self, client: AsyncClient, auth_headers: dict, test_guest: dict) -> None:
        response = await client.put(
            f"/api/v1/guests/{test_guest['id']}",
            json={"name": "Updated Guest Name"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Guest Name"
        # Unchanged fields should persist
        assert data["email"] == test_guest["email"]

    async def test_update_nationality_and_notes(
        self, client: AsyncClient, auth_headers: dict, test_guest: dict
    ) -> None:
        response = await client.put(
            f"/api/v1/guests/{test_guest['id']}",
            json={"nationality": "British", "notes": "Returning guest"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["nationality"] == "British"
        assert data["notes"] == "Returning guest"

    async def test_update_email_success(self, client: AsyncClient, auth_headers: dict, test_guest: dict) -> None:
        new_email = _unique_email()
        response = await client.put(
            f"/api/v1/guests/{test_guest['id']}",
            json={"email": new_email},
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["email"] == new_email

    async def test_update_email_uniqueness(self, client: AsyncClient, auth_headers: dict) -> None:
        """Changing a guest's email to one that already exists should fail."""
        email_a = _unique_email()
        email_b = _unique_email()

        resp_a = await client.post(
            "/api/v1/guests",
            json={"name": "Guest A", "email": email_a},
            headers=auth_headers,
        )
        assert resp_a.status_code == 201

        resp_b = await client.post(
            "/api/v1/guests",
            json={"name": "Guest B", "email": email_b},
            headers=auth_headers,
        )
        assert resp_b.status_code == 201
        guest_b_id = resp_b.json()["id"]

        # Try to update Guest B's email to Guest A's email
        response = await client.put(
            f"/api/v1/guests/{guest_b_id}",
            json={"email": email_a},
            headers=auth_headers,
        )
        assert response.status_code == 409
        assert "already exists" in response.json()["detail"].lower()

    async def test_update_not_found(self, client: AsyncClient, auth_headers: dict) -> None:
        fake_id = str(uuid.uuid4())
        response = await client.put(
            f"/api/v1/guests/{fake_id}",
            json={"name": "Ghost Guest"},
            headers=auth_headers,
        )
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /api/v1/guests/{guest_id}
# ---------------------------------------------------------------------------


class TestDeleteGuest:
    """Tests for deleting a guest."""

    async def test_delete_success(self, client: AsyncClient, auth_headers: dict) -> None:
        email = _unique_email()
        create_resp = await client.post(
            "/api/v1/guests",
            json={"name": "Deletable Guest", "email": email},
            headers=auth_headers,
        )
        assert create_resp.status_code == 201
        guest_id = create_resp.json()["id"]

        response = await client.delete(f"/api/v1/guests/{guest_id}", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["message"] == "Guest deleted"

        # Verify it's gone
        get_resp = await client.get(f"/api/v1/guests/{guest_id}", headers=auth_headers)
        assert get_resp.status_code == 404

    async def test_delete_not_found(self, client: AsyncClient, auth_headers: dict) -> None:
        fake_id = str(uuid.uuid4())
        response = await client.delete(f"/api/v1/guests/{fake_id}", headers=auth_headers)
        assert response.status_code == 404

    async def test_delete_guest_after_booking_removed(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_property: dict,
    ) -> None:
        """Deleting a guest succeeds once their bookings are removed first.

        Note: The Guest model's ``bookings`` relationship does not have
        ``cascade="all, delete-orphan"`` (unlike Property), so the ORM
        cannot cascade-delete bookings when a guest is removed via
        ``session.delete()``.  The DB-level ``ON DELETE CASCADE`` on
        ``bookings.guest_id`` would handle it for raw SQL, but the ORM
        intercepts first.  Therefore we delete bookings explicitly before
        deleting the guest.
        """
        # Create a guest
        email = _unique_email()
        guest_resp = await client.post(
            "/api/v1/guests",
            json={"name": "Cascade Guest", "email": email},
            headers=auth_headers,
        )
        assert guest_resp.status_code == 201
        guest_id = guest_resp.json()["id"]

        # Create a booking for that guest
        from datetime import date, timedelta

        ci = (date.today() + timedelta(days=300)).isoformat()
        co = (date.today() + timedelta(days=305)).isoformat()
        booking_resp = await client.post(
            "/api/v1/bookings",
            json={
                "property_id": test_property["id"],
                "guest_id": guest_id,
                "check_in": ci,
                "check_out": co,
            },
            headers=auth_headers,
        )
        assert booking_resp.status_code == 201
        booking_id = booking_resp.json()["id"]

        # Delete the booking first (ORM-level cascade not configured on Guest)
        del_booking = await client.delete(f"/api/v1/bookings/{booking_id}", headers=auth_headers)
        assert del_booking.status_code == 200

        # Now delete the guest
        del_resp = await client.delete(f"/api/v1/guests/{guest_id}", headers=auth_headers)
        assert del_resp.status_code == 200

        # Both should be gone
        get_guest = await client.get(f"/api/v1/guests/{guest_id}", headers=auth_headers)
        assert get_guest.status_code == 404

        get_booking = await client.get(f"/api/v1/bookings/{booking_id}", headers=auth_headers)
        assert get_booking.status_code == 404
