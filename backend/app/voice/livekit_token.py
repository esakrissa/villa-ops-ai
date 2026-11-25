"""LiveKit access tokens that dispatch the Villa voice agent.

A LiveKit token is an HS256 JWT signed with the project's API secret, so it is minted with
python-jose (already a dependency) instead of pulling in the livekit-api SDK. The claim layout
matches livekit-api's ``AccessToken.to_jwt()`` (checked in voice-agent/tests/test_token_format.py).

The agent dispatch metadata carries the user's id and conversation. Only the server holds the API
secret, so the agent can trust it: the browser can't change it, and the agent pins ``user_id`` on
every VillaOps tool call from it (the LLM never sees or chooses it).
"""

import json
import secrets
import time
import uuid
from dataclasses import dataclass

from jose import jwt

# How long a token can be used to join; the call itself may run longer.
TOKEN_TTL_S = 15 * 60
# LiveKit closes an empty room after this many seconds; the agent ends its session sooner itself.
DEPARTURE_TIMEOUT_S = 30


@dataclass(frozen=True)
class VoiceGrant:
    room_name: str
    identity: str
    token: str


def new_room_name() -> str:
    return f"villa-{secrets.token_hex(8)}"


def mint_voice_token(
    *,
    api_key: str,
    api_secret: str,
    agent_name: str,
    user_id: uuid.UUID,
    user_name: str | None,
    metadata: dict,
    room_name: str | None = None,
    now: float | None = None,
) -> VoiceGrant:
    """A token that joins one fresh room and dispatches ``agent_name`` into it with ``metadata``."""
    issued = int(now if now is not None else time.time())
    room = room_name or new_room_name()
    identity = f"user-{user_id.hex[:16]}-{secrets.token_hex(3)}"
    claims = {
        "iss": api_key,
        "sub": identity,
        "nbf": issued,
        "exp": issued + TOKEN_TTL_S,
        "name": user_name or "VillaOps user",
        "video": {
            "roomJoin": True,
            "room": room,
            "canPublish": True,
            "canSubscribe": True,
            "canPublishData": True,
        },
        "roomConfig": {
            "departureTimeout": DEPARTURE_TIMEOUT_S,
            "agents": [{"agentName": agent_name, "metadata": json.dumps(metadata)}],
        },
    }
    token = jwt.encode(claims, api_secret, algorithm="HS256")
    return VoiceGrant(room_name=room, identity=identity, token=token)
