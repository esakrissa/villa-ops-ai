"""FastAPI authentication dependencies for route protection."""

import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import decode_token
from app.database import get_db
from app.models.user import User

# Strict bearer — raises 403 automatically if no token provided
_bearer_scheme = HTTPBearer()

# Optional bearer — returns None if no token provided
_bearer_scheme_optional = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Extract and validate the Bearer token, then return the authenticated user.

    Raises:
        HTTPException 401: If the token is invalid, expired, wrong type, or user not found.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token = credentials.credentials

    try:
        payload = decode_token(token)
    except JWTError:
        raise credentials_exception from None

    # Only accept access tokens, not refresh tokens
    token_type: str | None = payload.get("type")
    if token_type != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Extract user ID from the subject claim
    sub: str | None = payload.get("sub")
    if sub is None:
        raise credentials_exception

    try:
        user_id = uuid.UUID(sub)
    except ValueError:
        raise credentials_exception from None

    # Query the user from the database
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


async def get_current_active_user(
    user: User = Depends(get_current_user),
) -> User:
    """Return the current user only if their account is active.

    Raises:
        HTTPException 403: If the user account is inactive or banned.
    """
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive",
        )
    return user


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme_optional),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """Optionally authenticate a user from a Bearer token.

    Returns ``None`` instead of raising when no token is provided.
    Useful for endpoints that work with or without authentication
    (e.g. public property listings that show extra info for logged-in users).
    """
    if credentials is None:
        return None

    token = credentials.credentials

    try:
        payload = decode_token(token)
    except JWTError:
        return None

    token_type: str | None = payload.get("type")
    if token_type != "access":
        return None

    sub: str | None = payload.get("sub")
    if sub is None:
        return None

    try:
        user_id = uuid.UUID(sub)
    except ValueError:
        return None

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        return None

    return user
