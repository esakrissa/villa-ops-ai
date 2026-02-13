"""Tests for OAuth helper functions (Google and GitHub user info extraction)."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.auth.oauth import get_github_user_info, get_google_user_info


class TestGetGoogleUserInfo:
    """Test get_google_user_info extracts standardized user info from token."""

    async def test_extracts_full_userinfo(self):
        token = {
            "userinfo": {
                "email": "alice@gmail.com",
                "name": "Alice Doe",
                "picture": "https://example.com/avatar.jpg",
                "sub": "google-uid-123",
            }
        }
        info = await get_google_user_info(token)
        assert info["email"] == "alice@gmail.com"
        assert info["name"] == "Alice Doe"
        assert info["avatar_url"] == "https://example.com/avatar.jpg"
        assert info["provider"] == "google"
        assert info["provider_id"] == "google-uid-123"

    async def test_handles_missing_fields(self):
        token = {"userinfo": {}}
        info = await get_google_user_info(token)
        assert info["email"] == ""
        assert info["name"] == ""
        assert info["avatar_url"] is None
        assert info["provider"] == "google"

    async def test_handles_no_userinfo(self):
        token = {}
        info = await get_google_user_info(token)
        assert info["email"] == ""
        assert info["provider"] == "google"


class TestGetGithubUserInfo:
    """Test get_github_user_info fetches user info from GitHub API."""

    async def test_extracts_user_with_email(self):
        mock_client = AsyncMock()
        profile_resp = MagicMock()
        profile_resp.json.return_value = {
            "email": "bob@github.com",
            "name": "Bob Smith",
            "avatar_url": "https://avatars.example.com/bob.jpg",
            "id": 42,
            "login": "bobsmith",
        }
        mock_client.get.return_value = profile_resp

        info = await get_github_user_info(mock_client, {"access_token": "tok"})
        assert info["email"] == "bob@github.com"
        assert info["name"] == "Bob Smith"
        assert info["avatar_url"] == "https://avatars.example.com/bob.jpg"
        assert info["provider"] == "github"
        assert info["provider_id"] == "42"

    async def test_fetches_email_from_emails_endpoint(self):
        """When profile email is empty, fetches /user/emails."""
        mock_client = AsyncMock()

        profile_resp = MagicMock()
        profile_resp.json.return_value = {
            "email": "",
            "name": "Private User",
            "avatar_url": None,
            "id": 99,
            "login": "privateuser",
        }

        emails_resp = MagicMock()
        emails_resp.json.return_value = [
            {"email": "secondary@example.com", "primary": False, "verified": True},
            {"email": "primary@example.com", "primary": True, "verified": True},
        ]

        mock_client.get.side_effect = [profile_resp, emails_resp]

        info = await get_github_user_info(mock_client, {"access_token": "tok"})
        assert info["email"] == "primary@example.com"
        assert info["name"] == "Private User"

    async def test_fallback_to_verified_email(self):
        """When no primary email, use first verified email."""
        mock_client = AsyncMock()

        profile_resp = MagicMock()
        profile_resp.json.return_value = {
            "email": None,
            "name": None,
            "avatar_url": None,
            "id": 100,
            "login": "noname",
        }

        emails_resp = MagicMock()
        emails_resp.json.return_value = [
            {"email": "unverified@example.com", "primary": False, "verified": False},
            {"email": "verified@example.com", "primary": False, "verified": True},
        ]

        mock_client.get.side_effect = [profile_resp, emails_resp]

        info = await get_github_user_info(mock_client, {})
        assert info["email"] == "verified@example.com"
        # Falls back to login when name is None
        assert info["name"] == "noname"

    async def test_no_emails_at_all(self):
        """When no verified emails found, email stays empty."""
        mock_client = AsyncMock()

        profile_resp = MagicMock()
        profile_resp.json.return_value = {
            "email": None,
            "name": "Ghost",
            "avatar_url": None,
            "id": 200,
            "login": "ghost",
        }

        emails_resp = MagicMock()
        emails_resp.json.return_value = []

        mock_client.get.side_effect = [profile_resp, emails_resp]

        info = await get_github_user_info(mock_client, {})
        assert info["email"] == ""
