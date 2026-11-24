"""Knowledge search shared by the dashboard API and the agent's MCP tool."""

import time
import uuid

from sqlalchemy import select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.knowledge.pinecone_client import get_pinecone, namespace_for
from app.models.knowledge import KnowledgeChunk, KnowledgeDocument


async def search_knowledge(session: AsyncSession, user_id: str, query: str, top_k: int = 5, rerank: bool = True) -> dict:
    """Search the user's documents. Returns ranked passages with citations.

    Pinecone ranks; Postgres supplies the passage text. A hit whose chunk no
    longer exists in Postgres (e.g. mid-delete) is dropped, so Postgres stays
    the source of truth for what the agent may cite.
    """
    started = time.perf_counter()
    owner = uuid.UUID(user_id)
    top_k = max(1, min(top_k, 10))
    hits = await get_pinecone().search(
        namespace_for(user_id),
        query,
        top_k=top_k,
        rerank=rerank,
        fields=["doc_id", "doc_name", "position", "heading", "page"],
    )

    pairs: list[tuple[dict, tuple[uuid.UUID, int]]] = []
    for h in hits:
        f = h["fields"]
        try:
            pairs.append((h, (uuid.UUID(str(f.get("doc_id"))), int(f.get("position")))))
        except (TypeError, ValueError):
            continue
    keys = [k for _, k in pairs]

    rows: dict[tuple[uuid.UUID, int], tuple[KnowledgeChunk, KnowledgeDocument]] = {}
    if keys:
        result = await session.execute(
            select(KnowledgeChunk, KnowledgeDocument)
            .join(KnowledgeDocument, KnowledgeChunk.document_id == KnowledgeDocument.id)
            .where(KnowledgeDocument.owner_id == owner)
            .where(tuple_(KnowledgeChunk.document_id, KnowledgeChunk.position).in_(keys))
        )
        rows = {(c.document_id, c.position): (c, d) for c, d in result.all()}

    results = []
    for h, key in pairs:
        if key not in rows:
            continue
        chunk, doc = rows[key]
        results.append(
            {
                "document": doc.name,
                "document_id": str(doc.id),
                "section": chunk.heading,
                "page": chunk.page,
                "chunk": chunk.position + 1,
                "score": round(float(h["score"] or 0), 4),
                "text": chunk.text,
            }
        )

    return {
        "query": query,
        "results": results,
        "total": len(results),
        "reranked": bool(rerank),
        "latency_ms": round((time.perf_counter() - started) * 1000),
    }
