"""Knowledge base API, pipeline and MCP tool tests — Pinecone is replaced by an in-memory fake."""

import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.knowledge import pipeline
from app.knowledge.pinecone_client import PineconeError, namespace_for, set_pinecone
from app.mcp import set_session_factory
from app.models.knowledge import KnowledgeChunk, KnowledgeDocument
from app.models.user import User

pytestmark = pytest.mark.asyncio

POLICY_MD = b"""# Booking Policy

## Cancellations
Free cancellation up to 14 days before arrival. 7 to 13 days before arrival: 50% refund.

## Pool
The pool is unsupervised. No glass near the pool.
"""


class FakePinecone:
    """In-memory stand-in: keyword-overlap 'search', records per namespace."""

    embed_model = "fake-embed"

    def __init__(self) -> None:
        self.namespaces: dict[str, dict[str, dict]] = {}
        self.deleted: list[tuple[str, list[str]]] = []
        self.fail_delete = False

    async def upsert_records(self, namespace: str, records: list[dict]) -> None:
        ns = self.namespaces.setdefault(namespace, {})
        for r in records:
            ns[r["_id"]] = dict(r)

    async def search(self, namespace, text, top_k=5, filter=None, rerank=True, fields=None):
        words = {w.lower().strip("?.,") for w in text.split()}
        hits = []
        for rid, rec in self.namespaces.get(namespace, {}).items():
            if filter and rec.get("doc_id") != filter["doc_id"]["$eq"]:
                continue
            body = {w.lower().strip("?.,:") for w in rec["chunk_text"].split()}
            score = len(words & body) / (len(words) or 1)
            hits.append({"id": rid, "score": score, "fields": {k: v for k, v in rec.items() if k != "chunk_text"}})
        hits.sort(key=lambda h: h["score"], reverse=True)
        return hits[:top_k]

    async def delete_ids(self, namespace: str, ids: list[str]) -> None:
        if self.fail_delete:
            raise PineconeError("Pinecone POST /vectors/delete → 500: boom")
        self.deleted.append((namespace, ids))
        for i in ids:
            self.namespaces.get(namespace, {}).pop(i, None)


class _SessionCtx:
    def __init__(self, session: AsyncSession):
        self._s = session

    async def __aenter__(self) -> AsyncSession:
        return self._s

    async def __aexit__(self, *args) -> None:
        pass


class _SessionFactory:
    def __init__(self, session: AsyncSession):
        self._s = session

    def __call__(self) -> _SessionCtx:
        return _SessionCtx(self._s)


@pytest.fixture
def fake_pc(monkeypatch):
    fake = FakePinecone()
    set_pinecone(fake)  # type: ignore[arg-type]
    monkeypatch.setattr(settings, "pinecone_api_key", "test-key")
    monkeypatch.setattr(pipeline, "VERIFY_TIMEOUT_S", 0.1)
    # Uploads shouldn't spawn real background tasks in tests
    monkeypatch.setattr(pipeline, "start_processing", lambda *_a, **_k: None)
    yield fake
    set_pinecone(None)


@pytest.fixture
def session_factory(db_session: AsyncSession, setup_test_db) -> _SessionFactory:
    factory = _SessionFactory(db_session)
    set_session_factory(factory)
    return factory


async def _ingest(db_session: AsyncSession, session_factory, fake_pc, owner: User, data: bytes = POLICY_MD) -> KnowledgeDocument:
    doc = KnowledgeDocument(owner_id=owner.id, name="Booking Policy.md", file_type="md", size_bytes=len(data))
    db_session.add(doc)
    await db_session.flush()
    await pipeline.process_document(doc.id, data, session_factory=session_factory, pinecone=fake_pc)
    db_session.expunge_all()
    return await db_session.get(KnowledgeDocument, doc.id)


@pytest_asyncio.fixture
async def other_user(db_session: AsyncSession) -> User:
    from app.auth.passwords import hash_password

    user = User(
        email=f"kb-other-{uuid.uuid4().hex[:8]}@test.com",
        hashed_password=hash_password("x"),
        name="Other",
        auth_provider="local",
        is_active=True,
        role="manager",
    )
    db_session.add(user)
    await db_session.flush()
    return user


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


class TestPipeline:
    async def test_ingest_creates_indexed_chunks(self, db_session, session_factory, fake_pc, test_user) -> None:
        doc = await _ingest(db_session, session_factory, fake_pc, test_user)
        assert doc.status == "ready"
        assert doc.error is None
        assert doc.chunk_count == doc.indexed_count == 2
        assert doc.embed_model == "fake-embed"
        assert doc.token_count > 0

        chunks = (await db_session.execute(select(KnowledgeChunk).where(KnowledgeChunk.document_id == doc.id))).scalars().all()
        assert sorted(c.position for c in chunks) == [0, 1]
        assert all(c.status == "indexed" for c in chunks)
        assert {c.heading for c in chunks} == {"Booking Policy \u203a Cancellations", "Booking Policy \u203a Pool"}

        records = fake_pc.namespaces[namespace_for(str(test_user.id))]
        assert set(records) == {f"{doc.id}#0", f"{doc.id}#1"}
        rec = records[f"{doc.id}#0"]
        assert rec["chunk_text"].startswith("Document: Booking Policy.md · Section: Booking Policy \u203a Cancellations")
        assert rec["doc_id"] == str(doc.id)

    async def test_ingest_failure_marks_failed(self, db_session, session_factory, fake_pc, test_user) -> None:
        doc = await _ingest(db_session, session_factory, fake_pc, test_user, data=b"   ")
        assert doc.status == "failed"
        assert "No readable text" in (doc.error or "")


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------


class TestKnowledgeApi:
    async def test_status(self, client: AsyncClient, auth_headers, fake_pc) -> None:
        resp = await client.get("/api/v1/knowledge/status", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["enabled"] is True
        assert "pdf" in body["supported_types"]

    async def test_requires_auth(self, client: AsyncClient) -> None:
        resp = await client.get("/api/v1/knowledge/documents")
        assert resp.status_code in (401, 403)

    async def test_upload_creates_queued_document(self, client: AsyncClient, auth_headers, fake_pc) -> None:
        resp = await client.post(
            "/api/v1/knowledge/documents",
            headers=auth_headers,
            files={"file": ("Booking Policy.md", POLICY_MD, "text/markdown")},
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["status"] == "queued"
        assert body["file_type"] == "md"
        assert body["size_bytes"] == len(POLICY_MD)

        listed = await client.get("/api/v1/knowledge/documents", headers=auth_headers)
        assert listed.json()["total"] == 1

    async def test_upload_rejects_unsupported_type(self, client: AsyncClient, auth_headers, fake_pc) -> None:
        resp = await client.post(
            "/api/v1/knowledge/documents",
            headers=auth_headers,
            files={"file": ("photo.png", b"\x89PNG", "image/png")},
        )
        assert resp.status_code == 415

    async def test_upload_rejects_empty_file(self, client: AsyncClient, auth_headers, fake_pc) -> None:
        resp = await client.post(
            "/api/v1/knowledge/documents",
            headers=auth_headers,
            files={"file": ("empty.txt", b"", "text/plain")},
        )
        assert resp.status_code == 400

    async def test_upload_rejects_too_large(self, client: AsyncClient, auth_headers, fake_pc, monkeypatch) -> None:
        monkeypatch.setattr(settings, "kb_max_upload_mb", 0)
        resp = await client.post(
            "/api/v1/knowledge/documents",
            headers=auth_headers,
            files={"file": ("big.txt", b"x" * 10, "text/plain")},
        )
        assert resp.status_code == 413

    async def test_upload_disabled_without_key(self, client: AsyncClient, auth_headers, monkeypatch) -> None:
        monkeypatch.setattr(settings, "pinecone_api_key", "")
        resp = await client.post(
            "/api/v1/knowledge/documents",
            headers=auth_headers,
            files={"file": ("a.md", b"# A\ntext", "text/markdown")},
        )
        assert resp.status_code == 503

    async def test_get_document_with_chunks(
        self, client: AsyncClient, auth_headers, db_session, session_factory, fake_pc, test_user
    ) -> None:
        doc = await _ingest(db_session, session_factory, fake_pc, test_user)
        resp = await client.get(f"/api/v1/knowledge/documents/{doc.id}", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ready"
        assert [c["position"] for c in body["chunks"]] == [0, 1]

    async def test_other_users_document_is_404(
        self, client: AsyncClient, auth_headers, db_session, session_factory, fake_pc, other_user
    ) -> None:
        doc = await _ingest(db_session, session_factory, fake_pc, other_user)
        assert (await client.get(f"/api/v1/knowledge/documents/{doc.id}", headers=auth_headers)).status_code == 404
        assert (await client.delete(f"/api/v1/knowledge/documents/{doc.id}", headers=auth_headers)).status_code == 404

    async def test_events_stream_for_finished_document(
        self, client: AsyncClient, auth_headers, db_session, session_factory, fake_pc, test_user
    ) -> None:
        doc = await _ingest(db_session, session_factory, fake_pc, test_user)
        # The stream opens its own sessions; point it at the test session
        import app.api.v1.knowledge as knowledge_api

        original = knowledge_api.async_session_factory
        knowledge_api.async_session_factory = session_factory  # type: ignore[assignment]
        try:
            resp = await client.get(f"/api/v1/knowledge/documents/{doc.id}/events", headers=auth_headers)
        finally:
            knowledge_api.async_session_factory = original
        assert resp.status_code == 200
        text = resp.text
        assert '"type": "chunks"' in text
        assert '"type": "indexed"' in text
        assert '"status": "ready"' in text

    async def test_delete_removes_vectors_then_rows(
        self, client: AsyncClient, auth_headers, db_session, session_factory, fake_pc, test_user
    ) -> None:
        doc = await _ingest(db_session, session_factory, fake_pc, test_user)
        doc_id = doc.id
        resp = await client.delete(f"/api/v1/knowledge/documents/{doc_id}", headers=auth_headers)
        assert resp.status_code == 204
        ns = namespace_for(str(test_user.id))
        assert fake_pc.deleted == [(ns, [f"{doc_id}#0", f"{doc_id}#1"])]
        assert fake_pc.namespaces[ns] == {}
        db_session.expunge_all()
        assert await db_session.get(KnowledgeDocument, doc_id) is None
        remaining = (await db_session.execute(select(KnowledgeChunk).where(KnowledgeChunk.document_id == doc_id))).all()
        assert remaining == []

    async def test_delete_keeps_rows_when_pinecone_fails(
        self, client: AsyncClient, auth_headers, db_session, session_factory, fake_pc, test_user
    ) -> None:
        doc = await _ingest(db_session, session_factory, fake_pc, test_user)
        doc_id = doc.id
        fake_pc.fail_delete = True
        resp = await client.delete(f"/api/v1/knowledge/documents/{doc_id}", headers=auth_headers)
        assert resp.status_code == 502
        db_session.expunge_all()
        assert await db_session.get(KnowledgeDocument, doc_id) is not None

    async def test_search_returns_cited_passages(
        self, client: AsyncClient, auth_headers, db_session, session_factory, fake_pc, test_user
    ) -> None:
        await _ingest(db_session, session_factory, fake_pc, test_user)
        resp = await client.post(
            "/api/v1/knowledge/search",
            headers=auth_headers,
            json={"query": "refund before arrival cancellation", "top_k": 2},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        top = body["results"][0]
        assert top["section"] == "Booking Policy \u203a Cancellations"
        assert top["document"] == "Booking Policy.md"
        assert "50% refund" in top["text"]
        assert not top["text"].startswith("Document:")  # clean text from Postgres, not the embedding header

    async def test_search_with_empty_kb(self, client: AsyncClient, auth_headers, fake_pc) -> None:
        resp = await client.post("/api/v1/knowledge/search", headers=auth_headers, json={"query": "anything"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 0


# ---------------------------------------------------------------------------
# MCP tools
# ---------------------------------------------------------------------------


class TestKnowledgeMcpTools:
    async def test_kb_search(self, db_session, session_factory, fake_pc, test_user) -> None:
        from app.mcp.tools.knowledge_tools import kb_search

        await _ingest(db_session, session_factory, fake_pc, test_user)
        result = await kb_search(query="is glass allowed near the pool", top_k=1, user_id=str(test_user.id))
        assert result["total"] == 1
        assert result["results"][0]["section"] == "Booking Policy \u203a Pool"

    async def test_kb_search_is_isolated_per_user(
        self, db_session, session_factory, fake_pc, test_user, other_user
    ) -> None:
        from app.mcp.tools.knowledge_tools import kb_search

        await _ingest(db_session, session_factory, fake_pc, test_user)
        result = await kb_search(query="pool glass", user_id=str(other_user.id))
        assert result["total"] == 0
        assert "empty" in result["note"]

    async def test_kb_search_requires_user(self, fake_pc) -> None:
        from app.mcp.tools.knowledge_tools import kb_search

        result = await kb_search(query="pool")
        assert result["error"] == "user_id is required."

    async def test_kb_list_documents(self, db_session, session_factory, fake_pc, test_user, other_user) -> None:
        from app.mcp.tools.knowledge_tools import kb_list_documents

        await _ingest(db_session, session_factory, fake_pc, test_user)
        mine = await kb_list_documents(user_id=str(test_user.id))
        assert mine["total"] == 1
        assert mine["documents"][0]["status"] == "ready"
        assert mine["documents"][0]["chunks"] == 2
        assert (await kb_list_documents(user_id=str(other_user.id)))["total"] == 0
