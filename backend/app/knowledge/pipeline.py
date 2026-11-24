"""Ingestion pipeline: extract → chunk → index in Pinecone → verify searchable.

Runs as a background task in the API process. Every stage writes its progress
to Postgres (document status, chunk rows, indexed counts), and the dashboard's
SSE stream reads it from there — so progress survives a page reload and works
with any number of API workers.
"""

import asyncio
import logging
import uuid
from collections.abc import Callable

from sqlalchemy import select, update

from app.config import settings
from app.database import async_session_factory
from app.knowledge.chunking import chunk_sections, embedding_text
from app.knowledge.extract import extract
from app.knowledge.pinecone_client import TEXT_FIELD, PineconeClient, get_pinecone, namespace_for
from app.models.knowledge import DOC_ACTIVE_STATUSES, KnowledgeChunk, KnowledgeDocument

logger = logging.getLogger(__name__)

INSERT_GROUP = 4  # chunk rows committed together (the UI shows them appearing)
INDEX_BATCH = 8  # chunks per Pinecone upsert (small, so indexing progress is visible)
VERIFY_TIMEOUT_S = 30.0  # Pinecone is eventually consistent; new records show up within seconds

_tasks: dict[uuid.UUID, asyncio.Task] = {}


def start_processing(document_id: uuid.UUID, data: bytes) -> None:
    """Schedule ingestion in the background (fire and forget)."""
    task = asyncio.create_task(process_document(document_id, data))
    _tasks[document_id] = task
    task.add_done_callback(lambda _t: _tasks.pop(document_id, None))


def cancel_processing(document_id: uuid.UUID) -> None:
    task = _tasks.pop(document_id, None)
    if task and not task.done():
        task.cancel()


async def _update_doc(session_factory: Callable, document_id: uuid.UUID, **values) -> None:
    async with session_factory() as session:
        await session.execute(update(KnowledgeDocument).where(KnowledgeDocument.id == document_id).values(**values))
        await session.commit()


async def process_document(
    document_id: uuid.UUID,
    data: bytes,
    session_factory: Callable = async_session_factory,
    pinecone: PineconeClient | None = None,
) -> None:
    pc = pinecone or get_pinecone()
    try:
        async with session_factory() as session:
            doc = await session.get(KnowledgeDocument, document_id)
            if doc is None:
                return
            owner_id, name, file_type = doc.owner_id, doc.name, doc.file_type

        # 1. Extract text (CPU-bound for big PDFs → thread)
        await _update_doc(session_factory, document_id, status="extracting")
        extracted = await asyncio.to_thread(extract, data, file_type)

        # 2. Chunk and store chunk rows
        await _update_doc(
            session_factory,
            document_id,
            status="chunking",
            page_count=extracted.page_count,
            char_count=extracted.char_count,
        )
        chunks = chunk_sections(extracted.sections, settings.kb_chunk_tokens, settings.kb_chunk_overlap_tokens)
        rows: list[KnowledgeChunk] = []
        for start in range(0, len(chunks), INSERT_GROUP):
            group = [
                KnowledgeChunk(
                    document_id=document_id,
                    position=start + i,
                    text=c.text,
                    heading=c.heading,
                    page=c.page,
                    token_count=c.token_count,
                )
                for i, c in enumerate(chunks[start : start + INSERT_GROUP])
            ]
            async with session_factory() as session:
                session.add_all(group)
                await session.execute(
                    update(KnowledgeDocument)
                    .where(KnowledgeDocument.id == document_id)
                    .values(chunk_count=start + len(group))
                )
                await session.commit()
            rows.extend(group)
            await asyncio.sleep(0)  # let the SSE poller see each group

        await _update_doc(
            session_factory,
            document_id,
            status="indexing",
            token_count=sum(c.token_count for c in chunks),
            embed_model=pc.embed_model,
        )

        # 3. Index in Pinecone (Pinecone embeds chunk_text with the index's model)
        namespace = namespace_for(str(owner_id))
        for start in range(0, len(rows), INDEX_BATCH):
            batch = rows[start : start + INDEX_BATCH]
            records = [
                {
                    "_id": f"{document_id}#{r.position}",
                    TEXT_FIELD: embedding_text(r.text, name, r.heading),
                    "doc_id": str(document_id),
                    "doc_name": name,
                    "position": r.position,
                    "heading": r.heading,
                    "page": r.page,
                }
                for r in batch
            ]
            await pc.upsert_records(namespace, records)
            async with session_factory() as session:
                await session.execute(
                    update(KnowledgeChunk)
                    .where(KnowledgeChunk.document_id == document_id)
                    .where(KnowledgeChunk.position.in_([r.position for r in batch]))
                    .values(status="indexed")
                )
                await session.execute(
                    update(KnowledgeDocument)
                    .where(KnowledgeDocument.id == document_id)
                    .values(indexed_count=start + len(batch))
                )
                await session.commit()

        # 4. Verify the document is actually searchable before calling it ready
        await _update_doc(session_factory, document_id, status="verifying")
        waited = 0.0
        while waited < VERIFY_TIMEOUT_S:
            hits = await pc.search(
                namespace, name, top_k=1, filter={"doc_id": {"$eq": str(document_id)}}, rerank=False
            )
            if hits:
                break
            await asyncio.sleep(1.5)
            waited += 1.5
        else:
            logger.warning("Document %s not visible in search after %ss; marking ready anyway", document_id, waited)

        await _update_doc(session_factory, document_id, status="ready", error=None)
        logger.info("Knowledge document %s indexed: %d chunks", document_id, len(rows))

    except asyncio.CancelledError:
        raise
    except Exception as e:
        logger.exception("Knowledge ingestion failed for %s", document_id)
        try:
            await _update_doc(session_factory, document_id, status="failed", error=str(e)[:500])
        except Exception:
            logger.exception("Couldn't mark document %s as failed", document_id)


async def delete_document_vectors(document_id: uuid.UUID, owner_id: uuid.UUID, positions: list[int]) -> None:
    """Remove a document's records from Pinecone (call before deleting the rows)."""
    ids = [f"{document_id}#{p}" for p in positions]
    await get_pinecone().delete_ids(namespace_for(str(owner_id)), ids)


async def fail_interrupted_documents() -> int:
    """On startup: documents left mid-pipeline by a restart can't resume (upload bytes are gone)."""
    async with async_session_factory() as session:
        result = await session.execute(
            update(KnowledgeDocument)
            .where(KnowledgeDocument.status.in_(DOC_ACTIVE_STATUSES))
            .values(status="failed", error="Interrupted by a server restart. Delete it and upload again.")
        )
        await session.commit()
        return result.rowcount or 0


async def chunk_positions(session, document_id: uuid.UUID) -> list[int]:
    result = await session.execute(select(KnowledgeChunk.position).where(KnowledgeChunk.document_id == document_id))
    return list(result.scalars().all())
