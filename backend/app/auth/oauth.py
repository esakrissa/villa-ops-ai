"""Google + GitHub OAuth configuration using authlib Starlette integration."""

from authlib.integrations.starlette_client import OAuth

from app.config import settings

oauth = OAuth()

# Google OAuth — OpenID Connect (auto-discovers endpoints)
oauth.register(
    name="google",
    client_id=settings.google_client_id,
    client_secret=settings.google_client_secret,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)

# GitHub OAuth — manual endpoint configuration
oauth.register(
    name="github",
    client_id=settings.github_client_id,
    client_secret=settings.github_client_secret,
    authorize_url="https://github.com/login/oauth/authorize",
    access_token_url="https://github.com/login/oauth/access_token",
    api_base_url="https://api.github.com/",
    client_kwargs={"scope": "user:email"},
)


async def get_google_user_info(token: dict) -> dict:
    """Extract standardized user info from a Google OAuth token response.

    Google uses OpenID Connect, so user info is available in the ID token's
    ``userinfo`` claim without an extra API call.

    Returns:
        dict with keys: email, name, avatar_url, provider, provider_id
    """
    userinfo = token.get("userinfo", {})
    return {
        "email": userinfo.get("email", ""),
        "name": userinfo.get("name", ""),
        "avatar_url": userinfo.get("picture"),
        "provider": "google",
        "provider_id": userinfo.get("sub", ""),
    }


async def get_github_user_info(client, token: dict) -> dict:  # noqa: ARG001 — token kept for API symmetry
    """Fetch standardized user info from the GitHub API.

    GitHub doesn't guarantee the email in the base ``/user`` response (users
    can make their email private), so we also fetch ``/user/emails`` and pick
    the primary verified address.

    Args:
        client: The authlib GitHub OAuth client (``oauth.github``).
        token: The OAuth token dict (used implicitly by the client session).

    Returns:
        dict with keys: email, name, avatar_url, provider, provider_id
    """
    # Fetch the authenticated user's profile
    resp = await client.get("user", token=token)
    profile = resp.json()

    email = profile.get("email") or ""

    # If the profile email is empty, fetch from /user/emails
    if not email:
        emails_resp = await client.get("user/emails", token=token)
        emails = emails_resp.json()
        # Find the primary verified email
        for entry in emails:
            if entry.get("primary") and entry.get("verified"):
                email = entry.get("email", "")
                break
        # Fallback: first verified email
        if not email:
            for entry in emails:
                if entry.get("verified"):
                    email = entry.get("email", "")
                    break

    return {
        "email": email,
        "name": profile.get("name") or profile.get("login", ""),
        "avatar_url": profile.get("avatar_url"),
        "provider": "github",
        "provider_id": str(profile.get("id", "")),
    }
