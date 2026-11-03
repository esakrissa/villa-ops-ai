"""Thin async client for the Tripadvisor Terra Partner API.

Terra replaced the legacy Content API (api.content.tripadvisor.com, ``?key=``):
requests go to terra.tripadvisor.com/api with an ``X-API-Key`` header.

Terra bills per location returned (search/nearby) or per location per call
(details/photos), and its caching policy forbids storing content, so this
client deliberately has no response cache. Keep ``size`` small.
"""

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://terra.tripadvisor.com/api"


class TripadvisorAPIError(Exception):
    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class TripadvisorClient:
    def __init__(self, api_key: str, timeout: float = 20.0) -> None:
        self._api_key = api_key
        self._timeout = timeout

    @property
    def configured(self) -> bool:
        return bool(self._api_key)

    async def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        if not self._api_key:
            raise TripadvisorAPIError("TRIPADVISOR_API_KEY is not set on the Tripadvisor MCP server.")
        query = {"version": 1, **{k: v for k, v in (params or {}).items() if v is not None}}
        logger.info("Terra request %s %s", path, query)
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.get(
                f"{BASE_URL}{path}",
                params=query,
                headers={"X-API-Key": self._api_key, "Accept": "application/json"},
            )
        if response.status_code == 200:
            return response.json()

        try:
            problem = response.json()
        except ValueError:
            problem = {}
        detail = problem.get("message") or problem.get("detail") or problem.get("title") or response.text[:200]
        if response.status_code == 429:
            detail = "Tripadvisor rate limit reached; try again in a minute."
        raise TripadvisorAPIError(f"Tripadvisor API returned {response.status_code}: {detail}", response.status_code)
