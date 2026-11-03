"""Thin async client for the RapidAPI Booking.com API (booking-com15)."""

import logging
from typing import Any

import httpx

from booking_com_mcp.cache import JsonCache

logger = logging.getLogger(__name__)


class BookingAPIError(Exception):
    """The API rejected the request (bad key, lapsed subscription, quota, bad params)."""


class BookingClient:
    def __init__(self, api_key: str, host: str, cache: JsonCache, timeout: float = 25.0) -> None:
        self._api_key = api_key
        self._host = host
        self._cache = cache
        self._timeout = timeout

    @property
    def configured(self) -> bool:
        return bool(self._api_key)

    async def get(self, endpoint: str, params: dict[str, Any], ttl: int) -> Any:
        """GET an endpoint and return its ``data`` payload, cached for ``ttl`` seconds."""
        if not self._api_key:
            raise BookingAPIError("RAPIDAPI_KEY is not set on the Booking.com MCP server.")

        key = self._cache.key(endpoint, params)
        cached = await self._cache.get(key)
        if cached is not None:
            logger.info("Cache hit for %s", endpoint)
            return cached

        logger.info("RapidAPI request %s %s", endpoint, params)
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.get(
                f"https://{self._host}{endpoint}",
                params=params,
                headers={"X-RapidAPI-Key": self._api_key, "X-RapidAPI-Host": self._host},
            )

        remaining = response.headers.get("x-ratelimit-requests-remaining")
        if remaining is not None:
            logger.info("RapidAPI requests remaining this period: %s", remaining)

        try:
            body = response.json()
        except ValueError:
            body = {}
        if response.status_code != 200:
            message = body.get("message") if isinstance(body, dict) else None
            raise BookingAPIError(f"Booking.com API returned {response.status_code}: {message or response.text[:200]}")
        if not isinstance(body, dict) or not body.get("status", False):
            message = body.get("message") if isinstance(body, dict) else "unexpected response"
            raise BookingAPIError(f"Booking.com API error: {message}")

        data = body.get("data")
        await self._cache.set(key, data, ttl)
        return data
