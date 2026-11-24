"""Thin async client for Pinecone's REST API (integrated embedding + reranking).

We call the REST API directly with httpx instead of the SDK: it is async,
adds no dependency, and pins one API version (``2025-04``) so SDK changes
can't break the demo. Pinecone embeds ``chunk_text`` server-side with the
index's model, so no embedding calls go through our LLM quota.
"""

import asyncio
import json
import logging
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

CONTROL_PLANE = "https://api.pinecone.io"
API_VERSION = "2025-04"
TEXT_FIELD = "chunk_text"
UPSERT_BATCH_MAX = 96  # Pinecone limit for records with integrated embedding


class PineconeError(RuntimeError):
    """Raised when a Pinecone call fails."""


def is_configured() -> bool:
    return bool(settings.pinecone_api_key)


def namespace_for(user_id: str) -> str:
    """Each user gets their own namespace, so searches never cross users."""
    return f"user-{user_id}"


class PineconeClient:
    """Minimal records API: ensure index, upsert, search, delete."""

    def __init__(self, api_key: str | None = None, index_name: str | None = None, embed_model: str | None = None):
        self.api_key = api_key or settings.pinecone_api_key
        self.index_name = index_name or settings.pinecone_index
        self.embed_model = embed_model or settings.pinecone_embed_model
        self._host: str | None = None

    def _headers(self, content_type: str = "application/json") -> dict[str, str]:
        return {
            "Api-Key": self.api_key,
            "X-Pinecone-API-Version": API_VERSION,
            "Content-Type": content_type,
        }

    async def _request(self, method: str, url: str, *, timeout: float = 30.0, **kwargs: Any) -> dict:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.request(method, url, **kwargs)
        if resp.status_code >= 400:
            raise PineconeError(f"Pinecone {method} {url.split('?')[0]} → {resp.status_code}: {resp.text[:300]}")
        if not resp.content:
            return {}
        try:
            return resp.json()
        except ValueError:
            return {}

    # -- control plane ------------------------------------------------------

    async def describe_index(self) -> dict | None:
        try:
            return await self._request("GET", f"{CONTROL_PLANE}/indexes/{self.index_name}", headers=self._headers())
        except PineconeError as e:
            if "→ 404" in str(e):
                return None
            raise

    async def ensure_index(self, wait_seconds: float = 90) -> str:
        """Return the index host, creating the integrated index on first use."""
        if self._host:
            return self._host

        info = await self.describe_index()
        if info is None:
            logger.info("Creating Pinecone index %s (model %s)", self.index_name, self.embed_model)
            await self._request(
                "POST",
                f"{CONTROL_PLANE}/indexes/create-for-model",
                headers=self._headers(),
                json={
                    "name": self.index_name,
                    "cloud": "aws",
                    "region": "us-east-1",  # the only region on Pinecone's Starter plan
                    "embed": {"model": self.embed_model, "field_map": {"text": TEXT_FIELD}},
                    "deletion_protection": "disabled",
                    "tags": {"app": "villaops"},
                },
            )
            info = await self.describe_index()

        waited = 0.0
        while info and not (info.get("status") or {}).get("ready"):
            if waited >= wait_seconds:
                raise PineconeError(f"Index {self.index_name} not ready after {wait_seconds}s")
            await asyncio.sleep(2)
            waited += 2
            info = await self.describe_index()

        if not info or not info.get("host"):
            raise PineconeError(f"Index {self.index_name} has no host")
        self._host = f"https://{info['host']}"
        return self._host

    # -- data plane ---------------------------------------------------------

    async def upsert_records(self, namespace: str, records: list[dict]) -> None:
        """Upsert records; each needs ``_id`` and ``chunk_text`` plus flat metadata."""
        if not records:
            return
        host = await self.ensure_index()
        for start in range(0, len(records), UPSERT_BATCH_MAX):
            batch = records[start : start + UPSERT_BATCH_MAX]
            body = "\n".join(json.dumps(_clean(r)) for r in batch)
            await self._request(
                "POST",
                f"{host}/records/namespaces/{namespace}/upsert",
                headers=self._headers("application/x-ndjson"),
                content=body,
                timeout=60.0,
            )

    async def search(
        self,
        namespace: str,
        text: str,
        top_k: int = 5,
        filter: dict | None = None,
        rerank: bool = True,
        fields: list[str] | None = None,
    ) -> list[dict]:
        """Semantic search; optionally rerank the candidates. Returns hits as dicts."""
        host = await self.ensure_index()
        candidates = max(top_k * 3, 10) if rerank and settings.pinecone_rerank_model else top_k
        query: dict[str, Any] = {"inputs": {"text": text}, "top_k": candidates}
        if filter:
            query["filter"] = filter
        body: dict[str, Any] = {"query": query}
        if fields:
            body["fields"] = fields
        if rerank and settings.pinecone_rerank_model:
            body["rerank"] = {
                "model": settings.pinecone_rerank_model,
                "rank_fields": [TEXT_FIELD],
                "top_n": top_k,
            }

        url = f"{host}/records/namespaces/{namespace}/search"
        try:
            data = await self._request("POST", url, headers=self._headers(), json=body)
        except PineconeError as e:
            # Free-tier rerank quota exhausted or model unavailable → plain vector search
            if "rerank" in body and any(code in str(e) for code in ("→ 429", "→ 403", "→ 400")):
                logger.warning("Rerank failed (%s); retrying without rerank", e)
                body.pop("rerank")
                query["top_k"] = top_k
                data = await self._request("POST", url, headers=self._headers(), json=body)
            else:
                raise

        hits = (data.get("result") or {}).get("hits") or []
        return [
            {"id": h.get("_id"), "score": h.get("_score"), "fields": h.get("fields") or {}}
            for h in hits[:top_k]
        ]

    async def delete_ids(self, namespace: str, ids: list[str]) -> None:
        if not ids:
            return
        host = await self.ensure_index()
        for start in range(0, len(ids), 1000):
            try:
                await self._request(
                    "POST",
                    f"{host}/vectors/delete",
                    headers=self._headers(),
                    json={"ids": ids[start : start + 1000], "namespace": namespace},
                )
            except PineconeError as e:
                # Deleting from a namespace that doesn't exist yet is fine
                if "→ 404" not in str(e):
                    raise


def _clean(record: dict) -> dict:
    """Pinecone metadata can't hold nulls — drop them."""
    return {k: v for k, v in record.items() if v is not None}


_client: PineconeClient | None = None


def get_pinecone() -> PineconeClient:
    """Process-wide client (caches the index host)."""
    global _client
    if _client is None:
        _client = PineconeClient()
    return _client


def set_pinecone(client: PineconeClient | None) -> None:
    """Override the client (tests)."""
    global _client
    _client = client
