"""Fetch Airbnb pages and pull out the JSON state they embed.

Airbnb server-renders search and listing pages with their GraphQL data in
``<script id="data-deferred-state-0">``. No API key is needed. Like the
original openbnb server, robots.txt is respected unless explicitly disabled.
"""

import json
import logging
import re
from typing import Any
from urllib.parse import urlencode
from urllib.robotparser import RobotFileParser

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://www.airbnb.com"
USER_AGENT = "ModelContextProtocol/1.0 (Autonomous; +https://github.com/modelcontextprotocol/servers)"
_STATE_SCRIPT = re.compile(r'<script id="data-deferred-state-0"[^>]*>(.*?)</script>', re.S)


class AirbnbError(Exception):
    """The page could not be fetched, was disallowed, or no longer has the expected structure."""


def extract_state(html: str) -> dict[str, Any]:
    """Return the GraphQL payload embedded in an Airbnb page."""
    match = _STATE_SCRIPT.search(html)
    if not match:
        raise AirbnbError("Airbnb page did not include listing data (the page layout may have changed).")
    state = json.loads(match.group(1))
    # Airbnb renamed niobeMinimalClientData → niobeClientData in 2026; accept both.
    for key in ("niobeClientData", "niobeMinimalClientData"):
        if state.get(key):
            return state[key][0][1]
    raise AirbnbError("Airbnb page data is in an unknown format.")


class AirbnbScraper:
    def __init__(self, ignore_robots_txt: bool = False, timeout: float = 20.0) -> None:
        self.ignore_robots_txt = ignore_robots_txt
        self._timeout = timeout
        self._robots: RobotFileParser | None = None

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            timeout=self._timeout,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"},
        )

    async def _is_allowed(self, url: str) -> bool:
        if self.ignore_robots_txt:
            return True
        if self._robots is None:
            parser = RobotFileParser()
            try:
                async with self._client() as client:
                    response = await client.get(f"{BASE_URL}/robots.txt")
                parser.parse(response.text.splitlines())
            except httpx.HTTPError:
                logger.warning("Could not fetch robots.txt; assuming allowed")
                parser.parse([])
            self._robots = parser
        return self._robots.can_fetch(USER_AGENT, url)

    async def fetch_state(self, path: str, params: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        """GET ``path`` with ``params`` and return ``(url, embedded_state)``."""
        query = urlencode({k: v for k, v in params.items() if v is not None})
        url = f"{BASE_URL}{path}?{query}" if query else f"{BASE_URL}{path}"
        if not await self._is_allowed(url):
            raise AirbnbError(
                "This Airbnb page is disallowed by robots.txt. "
                "Set AIRBNB_IGNORE_ROBOTS_TXT=true on the Airbnb MCP server to allow it."
            )
        logger.info("Fetching %s", url)
        async with self._client() as client:
            response = await client.get(url)
        if response.status_code != 200:
            raise AirbnbError(f"Airbnb returned HTTP {response.status_code}.")
        return url, extract_state(response.text)
