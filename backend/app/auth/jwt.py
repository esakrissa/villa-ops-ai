"""JWT token creation and verification for access and refresh tokens."""

from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

from app.config import settings


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Create a short-lived access token.

    Args:
        data: Payload data. Must include ``sub`` (user UUID as string).
        expires_delta: Custom expiration duration. Defaults to
            ``settings.jwt_access_token_expire_minutes`` minutes.

    Returns:
        Encoded JWT string.
    """
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(minutes=settings.jwt_access_token_expire_minutes))
    to_encode.update({"exp": expire, "iat": now, "type": "access"})
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Create a long-lived refresh token.

    Args:
        data: Payload data. Must include ``sub`` (user UUID as string).
        expires_delta: Custom expiration duration. Defaults to
            ``settings.jwt_refresh_token_expire_days`` days.

    Returns:
        Encoded JWT string.
    """
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(days=settings.jwt_refresh_token_expire_days))
    to_encode.update({"exp": expire, "iat": now, "type": "refresh"})
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    """Decode and verify a JWT token.

    Args:
        token: Encoded JWT string.

    Returns:
        Decoded payload dictionary.

    Raises:
        jose.JWTError: If the token is invalid, expired, or malformed.
    """
    return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])


def create_token_pair(user_id: str) -> dict[str, str]:
    """Create both access and refresh tokens for a user.

    Args:
        user_id: The user's UUID as a string.

    Returns:
        Dictionary with ``access_token``, ``refresh_token``, and ``token_type``.
    """
    payload = {"sub": user_id}
    return {
        "access_token": create_access_token(payload),
        "refresh_token": create_refresh_token(payload),
        "token_type": "bearer",
    }
