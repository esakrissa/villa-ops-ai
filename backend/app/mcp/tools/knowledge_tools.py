"""Knowledge base MCP tools — search and list the user's uploaded documents (RAG)."""

import logging
import uuid as uuid_mod

from sqlalchemy import select

from app.knowledge.pinecone_client import is_configured
from app.knowledge.search import search_knowledge
from app.mcp import get_session_factory, mcp
from app.models.knowledge import KnowledgeDocument

logger = logging.getLogger(__name__)


@mcp.tool()
async def kb_search(
    query: str,
    top_k: int = 5,
    user_id: str | None = None,
) -> dict:
    """Search the user's knowledge base (uploaded company documents, policies, handbooks).

    Use this for questions about the company's own rules and documents — privacy
    policy, house rules, cancellation/refund policy, staff procedures, SOPs.
    Answer only from the returned passages and cite them as (Document, section/page).

    Args:
        query: Natural-language question or keywords (e.g. "how long do we keep guest passport copies")
        top_k: Number of passages to return, 1-10 (default 5)
        user_id: UUID of the current user (required — searches only their documents)

    Returns:
        Dict with ranked passages (document, section, page, chunk, score, text) and total count.
    """
    if not user_id:
        return {"error": "user_id is required.", "results": [], "total": 0}
    if not is_configured():
        return {"error": "The knowledge base is not configured.", "results": [], "total": 0}

    try:
        session_factory = get_session_factory()
        async with session_factory() as session:
            owner = uuid_mod.UUID(user_id)
            has_docs = await session.scalar(
                select(KnowledgeDocument.id)
                .where(KnowledgeDocument.owner_id == owner, KnowledgeDocument.status == "ready")
                .limit(1)
            )
            if not has_docs:
                return {
                    "query": query,
                    "results": [],
                    "total": 0,
                    "note": "The knowledge base is empty. The user can upload documents on the Knowledge page.",
                }
            return await search_knowledge(session, user_id, query, top_k)
    except Exception as e:
        logger.exception("kb_search failed")
        return {"error": str(e), "results": [], "total": 0}


@mcp.tool()
async def kb_list_documents(user_id: str | None = None) -> dict:
    """List the documents in the user's knowledge base and whether each is ready to search.

    Use this when the user asks what documents or policies you have access to.

    Args:
        user_id: UUID of the current user (required — lists only their documents)

    Returns:
        Dict with documents (name, type, status, pages, chunks, uploaded_at) and total count.
    """
    if not user_id:
        return {"error": "user_id is required.", "documents": [], "total": 0}

    try:
        session_factory = get_session_factory()
        async with session_factory() as session:
            result = await session.execute(
                select(KnowledgeDocument)
                .where(KnowledgeDocument.owner_id == uuid_mod.UUID(user_id))
                .order_by(KnowledgeDocument.created_at.desc())
            )
            docs = list(result.scalars().all())
            return {
                "documents": [
                    {
                        "id": str(d.id),
                        "name": d.name,
                        "type": d.file_type,
                        "status": d.status,
                        "pages": d.page_count,
                        "chunks": d.chunk_count,
                        "uploaded_at": d.created_at.isoformat() if d.created_at else None,
                    }
                    for d in docs
                ],
                "total": len(docs),
            }
    except Exception as e:
        logger.exception("kb_list_documents failed")
        return {"error": str(e), "documents": [], "total": 0}
