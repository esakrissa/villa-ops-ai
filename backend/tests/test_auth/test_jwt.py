"""Unit tests for JWT token creation, decoding, and validation."""

from datetime import timedelta

import pytest
from jose import JWTError

from app.auth.jwt import (
    create_access_token,
    create_refresh_token,
    create_token_pair,
    decode_token,
)


class TestCreateAccessToken:
    """Test access token creation."""

    def test_contains_type_access(self):
        token = create_access_token({"sub": "user-123"})
        payload = decode_token(token)
        assert payload["type"] == "access"

    def test_contains_sub_claim(self):
        token = create_access_token({"sub": "user-abc"})
        payload = decode_token(token)
        assert payload["sub"] == "user-abc"

    def test_contains_iat_claim(self):
        token = create_access_token({"sub": "user-123"})
        payload = decode_token(token)
        assert "iat" in payload

    def test_contains_exp_claim(self):
        token = create_access_token({"sub": "user-123"})
        payload = decode_token(token)
        assert "exp" in payload

    def test_custom_expiry_delta(self):
        token = create_access_token({"sub": "user-123"}, expires_delta=timedelta(hours=1))
        payload = decode_token(token)
        # Token should be valid (not expired)
        assert payload["sub"] == "user-123"


class TestCreateRefreshToken:
    """Test refresh token creation."""

    def test_contains_type_refresh(self):
        token = create_refresh_token({"sub": "user-123"})
        payload = decode_token(token)
        assert payload["type"] == "refresh"

    def test_contains_sub_claim(self):
        token = create_refresh_token({"sub": "user-xyz"})
        payload = decode_token(token)
        assert payload["sub"] == "user-xyz"


class TestDecodeToken:
    """Test token decoding and validation."""

    def test_decode_valid_access_token(self):
        token = create_access_token({"sub": "user-123"})
        payload = decode_token(token)
        assert payload["sub"] == "user-123"
        assert payload["type"] == "access"

    def test_decode_expired_token_raises(self):
        token = create_access_token({"sub": "user-123"}, expires_delta=timedelta(seconds=-1))
        with pytest.raises(JWTError):
            decode_token(token)

    def test_decode_invalid_token_raises(self):
        with pytest.raises(JWTError):
            decode_token("not.a.valid.token")

    def test_decode_empty_string_raises(self):
        with pytest.raises(JWTError):
            decode_token("")


class TestCreateTokenPair:
    """Test token pair creation."""

    def test_returns_both_tokens(self):
        pair = create_token_pair("user-123")
        assert "access_token" in pair
        assert "refresh_token" in pair
        assert "token_type" in pair
        assert pair["token_type"] == "bearer"

    def test_access_token_is_access_type(self):
        pair = create_token_pair("user-123")
        payload = decode_token(pair["access_token"])
        assert payload["type"] == "access"
        assert payload["sub"] == "user-123"

    def test_refresh_token_is_refresh_type(self):
        pair = create_token_pair("user-123")
        payload = decode_token(pair["refresh_token"])
        assert payload["type"] == "refresh"
        assert payload["sub"] == "user-123"
