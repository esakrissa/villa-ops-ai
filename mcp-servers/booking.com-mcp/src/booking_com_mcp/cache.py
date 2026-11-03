"""Redis-backed JSON cache that degrades to no caching when Redis is unavailable.

The RapidAPI free plan has a small monthly quota, so identical searches
(same destination, dates, guests, currency) are served from Redis.
"""

import hashlib
import json
import logging
from typing import Any

import redis.asyncio as redis

logger = logging.getLogger(__name__)


class JsonCache:
    def __init__(self, url: str | None, prefix: str) -> None:
        self._prefix = prefix
        self._client: redis.Redis | None = redis.from_url(url, decode_responses=True) if url else None
        self._warned = False

    def key(self, name: str, params: dict[str, Any]) -> str:
        digest = hashlib.sha1(json.dumps(params, sort_keys=True, default=str).encode()).hexdigest()[:20]
        return f"{self._prefix}:{name}:{digest}"

    async def get(self, key: str) -> Any | None:
        if self._client is None:
            return None
        try:
            raw = await self._client.get(key)
        except Exception as e:
            self._warn(e)
            return None
        return json.loads(raw) if raw else None

    async def set(self, key: str, value: Any, ttl: int) -> None:
        if self._client is None:
            return
        try:
            await self._client.set(key, json.dumps(value), ex=ttl)
        except Exception as e:
            self._warn(e)

    def _warn(self, error: Exception) -> None:
        if not self._warned:
            logger.warning("Redis cache unavailable, continuing without cache: %s", error)
            self._warned = True
