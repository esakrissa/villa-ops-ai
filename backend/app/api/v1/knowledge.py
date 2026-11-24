"""Knowledge base API — upload documents, watch them get chunked and indexed, search, delete."""

import asyncio
import json
import logging
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse
from starlette.requests import Request

from app.api.deps import get_current_active_user, get_db
from app.config import settings
from app.database import async_session_factory
from app.knowledge import pipeline
from app.knowledge.extract import SUPPORTED_TYPES, file_type_for
from app.knowledge.pinecone_client import PineconeError, is_configured
from app.knowledge.search import search_knowledge
from app.models.knowledge import DOC_TERMINAL_STATUSES, KnowledgeChunk, KnowledgeDocument
from app.models.user import User
from app.schemas.knowledge import (
    KnowledgeChunkResponse,
    KnowledgeDocumentDetail,
    KnowledgeDocumentList,
    KnowledgeDocumentResponse,
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
    KnowledgeStatus,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/knowledge", tags=["knowledge"])

EVENTS_POLL_S = 0.35
EVENTS_MAX_S = 600


def _require_enabled() -> None:
    if not is_configured():
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Knowledge base is not configured (PINECONE_API_KEY).")


async def _get_owned(db: AsyncSession, document_id: uuid.UUID, user: User) -> KnowledgeDocument:
    doc = await db.get(KnowledgeDocument, document_id)
    if doc is None or doc.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    return doc


@router.get("/status", response_model=KnowledgeStatus, summary="Knowledge base configuration")
async def knowledge_status(_user: User = Depends(get_current_active_user)) -> KnowledgeStatus:
    return KnowledgeStatus(
        enabled=is_configured(),
        index=settings.pinecone_index,
        embed_model=settings.pinecone_embed_model,
        rerank_model=settings.pinecone_rerank_model or None,
        max_upload_mb=settings.kb_max_upload_mb,
        supported_types=sorted(set(SUPPORTED_TYPES)),
        chunk_tokens=settings.kb_chunk_tokens,
        overlap_tokens=settings.kb_chunk_overlap_tokens,
    )


@router.get("/documents", response_model=KnowledgeDocumentList, summary="List knowledge documents")
async def list_documents(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> KnowledgeDocumentList:
    result = await db.execute(
        select(KnowledgeDocument)
        .where(KnowledgeDocument.owner_id == current_user.id)
        .order_by(KnowledgeDocument.created_at.desc())
    )
    items = list(result.scalars().all())
    return KnowledgeDocumentList(
        items=[KnowledgeDocumentResponse.model_validate(d) for d in items],
        total=len(items),
    )


@router.post(
    "/documents",
    response_model=KnowledgeDocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a document and start indexing it",
)
async def upload_document(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> KnowledgeDocumentResponse:
    _require_enabled()
    filename = (file.filename or "document").strip()[:255]
    file_type = file_type_for(filename)
    if file_type is None:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            "Unsupported file type. Upload a PDF, DOCX, Markdown or text file.",
        )

    max_bytes = settings.kb_max_upload_mb * 1024 * 1024
    data = await file.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise HTTPException(413, f"File is larger than {settings.kb_max_upload_mb} MB.")
    if not data:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "File is empty.")

    doc = KnowledgeDocument(
        owner_id=current_user.id,
        name=filename,
        file_type=file_type,
        size_bytes=len(data),
        status="queued",
    )
    db.add(doc)
    await db.flush()
    await db.refresh(doc)
    # Commit now so the background task (separate session) can see the row
    await db.commit()

    pipeline.start_processing(doc.id, data)
    return KnowledgeDocumentResponse.model_validate(doc)


@router.get("/documents/{document_id}", response_model=KnowledgeDocumentDetail, summary="Document with its chunks")
async def get_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> KnowledgeDocumentDetail:
    doc = await _get_owned(db, document_id, current_user)
    result = await db.execute(
        select(KnowledgeChunk).where(KnowledgeChunk.document_id == doc.id).order_by(KnowledgeChunk.position)
    )
    chunks = [KnowledgeChunkResponse.model_validate(c) for c in result.scalars().all()]
    return KnowledgeDocumentDetail(**KnowledgeDocumentResponse.model_validate(doc).model_dump(), chunks=chunks)


@router.get("/documents/{document_id}/events", summary="Live ingestion progress (SSE)")
async def document_events(
    document_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> EventSourceResponse:
    """Stream ingestion progress: document status, new chunks, newly indexed chunks.

    Events (JSON in ``data``):
    - ``{"type": "document", "document": {...}}`` — status/counters changed
    - ``{"type": "chunks", "chunks": [...]}`` — chunks created since last event
    - ``{"type": "indexed", "positions": [...]}`` — chunks now stored in Pinecone
    - ``{"type": "done", "status": "ready"|"failed"}``
    """
    await _get_owned(db, document_id, current_user)

    async def event_generator():
        sent_positions: set[int] = set()
        indexed_positions: set[int] = set()
        last_doc: dict | None = None
        elapsed = 0.0

        while elapsed < EVENTS_MAX_S:
            if await request.is_disconnected():
                return
            # Fresh session per poll — never reuse the request's session in a stream
            async with async_session_factory() as session:
                doc = await session.get(KnowledgeDocument, document_id)
                if doc is None:
                    yield {"data": json.dumps({"type": "done", "status": "deleted"})}
                    return
                doc_data = KnowledgeDocumentResponse.model_validate(doc).model_dump(mode="json")
                result = await session.execute(
                    select(KnowledgeChunk)
                    .where(KnowledgeChunk.document_id == document_id)
                    .order_by(KnowledgeChunk.position)
                )
                chunks = list(result.scalars().all())

            new_chunks = [c for c in chunks if c.position not in sent_positions]
            if new_chunks:
                sent_positions.update(c.position for c in new_chunks)
                payload = [KnowledgeChunkResponse.model_validate(c).model_dump(mode="json") for c in new_chunks]
                yield {"data": json.dumps({"type": "chunks", "chunks": payload})}

            newly_indexed = [c.position for c in chunks if c.status == "indexed" and c.position not in indexed_positions]
            if newly_indexed:
                indexed_positions.update(newly_indexed)
                yield {"data": json.dumps({"type": "indexed", "positions": newly_indexed})}

            if doc_data != last_doc:
                last_doc = doc_data
                yield {"data": json.dumps({"type": "document", "document": doc_data})}

            if doc_data["status"] in DOC_TERMINAL_STATUSES:
                yield {"data": json.dumps({"type": "done", "status": doc_data["status"]})}
                return

            await asyncio.sleep(EVENTS_POLL_S)
            elapsed += EVENTS_POLL_S

    return EventSourceResponse(event_generator(), ping=15)


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Remove a document")
async def delete_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> None:
    """Delete from Pinecone first, then Postgres — if Pinecone fails, nothing is lost and you can retry."""
    doc = await _get_owned(db, document_id, current_user)
    pipeline.cancel_processing(doc.id)
    positions = await pipeline.chunk_positions(db, doc.id)
    if positions and is_configured():
        try:
            await pipeline.delete_document_vectors(doc.id, doc.owner_id, positions)
        except PineconeError as e:
            logger.exception("Pinecone delete failed for %s", doc.id)
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Couldn't remove it from the vector index: {e}") from e
    await db.delete(doc)
    await db.flush()


@router.post("/search", response_model=KnowledgeSearchResponse, summary="Search the knowledge base")
async def search(
    body: KnowledgeSearchRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> KnowledgeSearchResponse:
    _require_enabled()
    count = await db.scalar(
        select(func.count()).select_from(KnowledgeDocument).where(KnowledgeDocument.owner_id == current_user.id)
    )
    if not count:
        return KnowledgeSearchResponse(query=body.query, results=[], total=0, reranked=False, latency_ms=0)
    try:
        data = await search_knowledge(db, str(current_user.id), body.query, body.top_k, body.rerank)
    except PineconeError as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(e)) from e
    return KnowledgeSearchResponse(**data)
