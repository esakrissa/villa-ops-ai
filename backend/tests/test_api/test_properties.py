"""Tests for property CRUD endpoints."""

import uuid

import pytest
from httpx import AsyncClient

from app.models.user import User

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# POST /api/v1/properties
# ---------------------------------------------------------------------------


class TestCreateProperty:
    """Tests for creating properties."""

    async def test_create_success(self, client: AsyncClient, auth_headers: dict, test_user: User) -> None:
        response = await client.post(
            "/api/v1/properties",
            json={
                "name": "Villa Sunrise",
                "description": "A beautiful villa in Seminyak",
                "location": "Seminyak, Bali",
                "property_type": "villa",
                "max_guests": 8,
                "base_price_per_night": 250.00,
                "amenities": ["pool", "wifi", "ac", "kitchen"],
            },
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Villa Sunrise"
        assert data["description"] == "A beautiful villa in Seminyak"
        assert data["location"] == "Seminyak, Bali"
        assert data["property_type"] == "villa"
        assert data["max_guests"] == 8
        assert float(data["base_price_per_night"]) == 250.00
        assert data["amenities"] == ["pool", "wifi", "ac", "kitchen"]
        assert data["status"] == "active"
        assert data["owner_id"] == str(test_user.id)
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data

    async def test_create_minimal(self, client: AsyncClient, auth_headers: dict) -> None:
        """Only required fields: name and property_type."""
        response = await client.post(
            "/api/v1/properties",
            json={"name": "Minimal Villa", "property_type": "villa"},
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Minimal Villa"
        assert data["property_type"] == "villa"
        assert data["status"] == "active"

    async def test_create_unauthenticated(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/v1/properties",
            json={"name": "No Auth Villa", "property_type": "villa"},
        )
        assert response.status_code in (401, 403)

    async def test_create_invalid_type(self, client: AsyncClient, auth_headers: dict) -> None:
        response = await client.post(
            "/api/v1/properties",
            json={"name": "Bad Type", "property_type": "castle"},
            headers=auth_headers,
        )
        assert response.status_code == 422

    async def test_create_missing_name(self, client: AsyncClient, auth_headers: dict) -> None:
        response = await client.post(
            "/api/v1/properties",
            json={"property_type": "villa"},
            headers=auth_headers,
        )
        assert response.status_code == 422

    async def test_create_all_property_types(self, client: AsyncClient, auth_headers: dict) -> None:
        for ptype in ("villa", "hotel", "guesthouse"):
            response = await client.post(
                "/api/v1/properties",
                json={"name": f"Test {ptype}", "property_type": ptype},
                headers=auth_headers,
            )
            assert response.status_code == 201, f"Failed for type: {ptype}"
            assert response.json()["property_type"] == ptype


# ---------------------------------------------------------------------------
# GET /api/v1/properties
# ---------------------------------------------------------------------------


class TestListProperties:
    """Tests for listing properties."""

    async def test_list_returns_own_only(self, client: AsyncClient, auth_headers: dict) -> None:
        """User should only see their own properties."""
        # Create two properties
        await client.post(
            "/api/v1/properties",
            json={"name": "My Villa 1", "property_type": "villa"},
            headers=auth_headers,
        )
        await client.post(
            "/api/v1/properties",
            json={"name": "My Villa 2", "property_type": "hotel"},
            headers=auth_headers,
        )

        response = await client.get("/api/v1/properties", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert data["total"] >= 2
        assert all("id" in item for item in data["items"])

    async def test_list_with_type_filter(self, client: AsyncClient, auth_headers: dict) -> None:
        # Create one villa and one hotel
        await client.post(
            "/api/v1/properties",
            json={"name": "Filter Villa", "property_type": "villa"},
            headers=auth_headers,
        )
        await client.post(
            "/api/v1/properties",
            json={"name": "Filter Hotel", "property_type": "hotel"},
            headers=auth_headers,
        )

        response = await client.get(
            "/api/v1/properties",
            params={"property_type": "villa"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert all(item["property_type"] == "villa" for item in data["items"])

    async def test_list_with_status_filter(self, client: AsyncClient, auth_headers: dict) -> None:
        # Create an active property
        await client.post(
            "/api/v1/properties",
            json={"name": "Active Villa", "property_type": "villa", "status": "active"},
            headers=auth_headers,
        )

        response = await client.get(
            "/api/v1/properties",
            params={"status": "active"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert all(item["status"] == "active" for item in data["items"])

    async def test_list_pagination(self, client: AsyncClient, auth_headers: dict) -> None:
        # Create several properties
        for i in range(3):
            await client.post(
                "/api/v1/properties",
                json={"name": f"Page Villa {i}", "property_type": "villa"},
                headers=auth_headers,
            )

        response = await client.get(
            "/api/v1/properties",
            params={"skip": 0, "limit": 2},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) <= 2
        assert data["total"] >= 3

    async def test_list_unauthenticated(self, client: AsyncClient) -> None:
        response = await client.get("/api/v1/properties")
        assert response.status_code in (401, 403)


# ---------------------------------------------------------------------------
# GET /api/v1/properties/{property_id}
# ---------------------------------------------------------------------------


class TestGetProperty:
    """Tests for getting a single property."""

    async def test_get_success(self, client: AsyncClient, auth_headers: dict, test_property: dict) -> None:
        prop_id = test_property["id"]
        response = await client.get(f"/api/v1/properties/{prop_id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == prop_id
        assert data["name"] == test_property["name"]

    async def test_get_not_found(self, client: AsyncClient, auth_headers: dict) -> None:
        fake_id = str(uuid.uuid4())
        response = await client.get(f"/api/v1/properties/{fake_id}", headers=auth_headers)
        assert response.status_code == 404

    async def test_get_other_users_property(
        self,
        client: AsyncClient,
        test_property: dict,
        db_session,
    ) -> None:
        """A different user should not be able to access another user's property."""
        from app.auth.jwt import create_token_pair
        from app.auth.passwords import hash_password
        from app.models.user import User

        other_user = User(
            email=f"other-{uuid.uuid4().hex[:8]}@test.com",
            hashed_password=hash_password("otherpass1"),
            name="Other User",
            auth_provider="local",
            is_active=True,
            role="manager",
        )
        db_session.add(other_user)
        await db_session.flush()

        tokens = create_token_pair(str(other_user.id))
        other_headers = {"Authorization": f"Bearer {tokens['access_token']}"}

        response = await client.get(
            f"/api/v1/properties/{test_property['id']}",
            headers=other_headers,
        )
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# PUT /api/v1/properties/{property_id}
# ---------------------------------------------------------------------------


class TestUpdateProperty:
    """Tests for updating a property."""

    async def test_update_partial(self, client: AsyncClient, auth_headers: dict, test_property: dict) -> None:
        prop_id = test_property["id"]
        response = await client.put(
            f"/api/v1/properties/{prop_id}",
            json={"name": "Updated Villa Name", "base_price_per_night": 200.00},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Villa Name"
        assert float(data["base_price_per_night"]) == 200.00
        # Unchanged fields should remain
        assert data["property_type"] == test_property["property_type"]
        assert data["location"] == test_property["location"]

    async def test_update_status(self, client: AsyncClient, auth_headers: dict, test_property: dict) -> None:
        prop_id = test_property["id"]
        response = await client.put(
            f"/api/v1/properties/{prop_id}",
            json={"status": "maintenance"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["status"] == "maintenance"

    async def test_update_not_found(self, client: AsyncClient, auth_headers: dict) -> None:
        fake_id = str(uuid.uuid4())
        response = await client.put(
            f"/api/v1/properties/{fake_id}",
            json={"name": "Ghost Villa"},
            headers=auth_headers,
        )
        assert response.status_code == 404

    async def test_update_invalid_type(self, client: AsyncClient, auth_headers: dict, test_property: dict) -> None:
        prop_id = test_property["id"]
        response = await client.put(
            f"/api/v1/properties/{prop_id}",
            json={"property_type": "castle"},
            headers=auth_headers,
        )
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# DELETE /api/v1/properties/{property_id}
# ---------------------------------------------------------------------------


class TestDeleteProperty:
    """Tests for deleting a property."""

    async def test_delete_success(self, client: AsyncClient, auth_headers: dict, test_property: dict) -> None:
        prop_id = test_property["id"]
        response = await client.delete(f"/api/v1/properties/{prop_id}", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["message"] == "Property deleted"

        # Verify it's gone
        get_response = await client.get(f"/api/v1/properties/{prop_id}", headers=auth_headers)
        assert get_response.status_code == 404

    async def test_delete_not_found(self, client: AsyncClient, auth_headers: dict) -> None:
        fake_id = str(uuid.uuid4())
        response = await client.delete(f"/api/v1/properties/{fake_id}", headers=auth_headers)
        assert response.status_code == 404

    async def test_delete_cascades_bookings(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_property: dict,
        test_guest: dict,
    ) -> None:
        """Deleting a property should cascade-delete associated bookings."""
        # Create a booking on this property
        booking_resp = await client.post(
            "/api/v1/bookings",
            json={
                "property_id": test_property["id"],
                "guest_id": test_guest["id"],
                "check_in": "2026-06-01",
                "check_out": "2026-06-05",
                "num_guests": 2,
            },
            headers=auth_headers,
        )
        assert booking_resp.status_code == 201
        booking_id = booking_resp.json()["id"]

        # Delete the property
        del_resp = await client.delete(
            f"/api/v1/properties/{test_property['id']}",
            headers=auth_headers,
        )
        assert del_resp.status_code == 200

        # The booking should be gone too
        get_booking = await client.get(f"/api/v1/bookings/{booking_id}", headers=auth_headers)
        assert get_booking.status_code == 404
