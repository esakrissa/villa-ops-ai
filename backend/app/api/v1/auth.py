"""Auth API router — register, login, refresh, me, Google OAuth, GitHub OAuth."""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_active_user
from app.auth.jwt import create_token_pair, decode_token
from app.auth.oauth import get_github_user_info, get_google_user_info, oauth
from app.auth.passwords import hash_password, verify_password
from app.config import settings
from app.database import get_db
from app.models.subscription import Subscription
from app.models.user import User
from app.schemas.auth import (
    AuthResponse,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


# ---------------------------------------------------------------------------
# Helper: find-or-create user from OAuth provider info
# ---------------------------------------------------------------------------


async def _find_or_create_oauth_user(
    db: AsyncSession,
    email: str,
    name: str,
    avatar_url: str | None,
    provider: str,
    provider_id: str,
) -> User:
    """Look up user by email; create if missing, update OAuth fields if found."""
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if user is not None:
        # Existing user — update OAuth fields (handles provider migration too)
        user.auth_provider = provider
        user.auth_provider_id = provider_id
        if avatar_url:
            user.avatar_url = avatar_url
        db.add(user)
        await db.flush()
        return user

    # New user — create User + free Subscription
    user = User(
        email=email,
        name=name,
        avatar_url=avatar_url,
        auth_provider=provider,
        auth_provider_id=provider_id,
        hashed_password=None,
    )
    db.add(user)
    await db.flush()

    subscription = Subscription(user_id=user.id, plan="free", status="active")
    db.add(subscription)
    await db.flush()

    # Refresh so relationships are loaded
    await db.refresh(user)
    return user


# ---------------------------------------------------------------------------
# POST /register
# ---------------------------------------------------------------------------


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)) -> AuthResponse:
    """Register a new user with email and password."""
    # Check for existing email
    result = await db.execute(select(User).where(User.email == body.email))
    existing = result.scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    # Create user
    user = User(
        email=body.email,
        hashed_password=hash_password(body.password),
        name=body.name,
        auth_provider="local",
    )
    db.add(user)
    await db.flush()

    # Create free subscription
    subscription = Subscription(user_id=user.id, plan="free", status="active")
    db.add(subscription)
    await db.flush()

    # Refresh to load relationships
    await db.refresh(user)

    # Generate tokens
    tokens = create_token_pair(str(user.id))

    return AuthResponse(
        user=UserResponse.model_validate(user),
        tokens=TokenResponse(**tokens),
    )


# ---------------------------------------------------------------------------
# POST /login
# ---------------------------------------------------------------------------


@router.post("/login", response_model=AuthResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)) -> AuthResponse:
    """Authenticate with email and password."""
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    # Reject: not found, OAuth-only account (no password), or wrong password
    if user is None or user.hashed_password is None or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive",
        )

    tokens = create_token_pair(str(user.id))

    return AuthResponse(
        user=UserResponse.model_validate(user),
        tokens=TokenResponse(**tokens),
    )


# ---------------------------------------------------------------------------
# POST /refresh
# ---------------------------------------------------------------------------


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    """Exchange a valid refresh token for a new token pair."""
    try:
        payload = decode_token(body.refresh_token)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id_str = payload.get("sub")
    if user_id_str is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )

    tokens = create_token_pair(str(user.id))
    return TokenResponse(**tokens)


# ---------------------------------------------------------------------------
# GET /me
# ---------------------------------------------------------------------------


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_active_user)) -> UserResponse:
    """Return the currently authenticated user's profile."""
    return UserResponse.model_validate(current_user)


# ---------------------------------------------------------------------------
# Google OAuth
# ---------------------------------------------------------------------------


@router.get("/google")
async def google_login(request: Request) -> RedirectResponse:
    """Redirect to Google's OAuth consent screen."""
    return await oauth.google.authorize_redirect(request, settings.google_redirect_uri)  # type: ignore[return-value]


@router.get("/google/callback")
async def google_callback(request: Request, db: AsyncSession = Depends(get_db)) -> RedirectResponse:
    """Handle Google OAuth callback — find or create user, redirect to frontend with tokens."""
    try:
        token = await oauth.google.authorize_access_token(request)
    except Exception as exc:
        logger.warning("Google OAuth callback failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google authentication failed. Please try again.",
        ) from None

    user_info = await get_google_user_info(token)

    user = await _find_or_create_oauth_user(
        db=db,
        email=user_info["email"],
        name=user_info["name"],
        avatar_url=user_info.get("avatar_url"),
        provider="google",
        provider_id=user_info["provider_id"],
    )

    tokens = create_token_pair(str(user.id))

    redirect_url = (
        f"{settings.frontend_url}/auth/callback"
        f"?access_token={tokens['access_token']}"
        f"&refresh_token={tokens['refresh_token']}"
    )
    return RedirectResponse(url=redirect_url)


# ---------------------------------------------------------------------------
# GitHub OAuth
# ---------------------------------------------------------------------------


@router.get("/github")
async def github_login(request: Request) -> RedirectResponse:
    """Redirect to GitHub's OAuth consent screen."""
    return await oauth.github.authorize_redirect(request, settings.github_redirect_uri)  # type: ignore[return-value]


@router.get("/github/callback")
async def github_callback(request: Request, db: AsyncSession = Depends(get_db)) -> RedirectResponse:
    """Handle GitHub OAuth callback — find or create user, redirect to frontend with tokens."""
    try:
        token = await oauth.github.authorize_access_token(request)
    except Exception as exc:
        logger.warning("GitHub OAuth callback failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="GitHub authentication failed. Please try again.",
        ) from None

    user_info = await get_github_user_info(oauth.github, token)

    user = await _find_or_create_oauth_user(
        db=db,
        email=user_info["email"],
        name=user_info["name"],
        avatar_url=user_info.get("avatar_url"),
        provider="github",
        provider_id=user_info["provider_id"],
    )

    tokens = create_token_pair(str(user.id))

    redirect_url = (
        f"{settings.frontend_url}/auth/callback"
        f"?access_token={tokens['access_token']}"
        f"&refresh_token={tokens['refresh_token']}"
    )
    return RedirectResponse(url=redirect_url)
