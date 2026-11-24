"""Knowledge base models — uploaded documents and their chunks.

Postgres is the source of truth for what a user has uploaded (names, status,
chunk text for the dashboard). Pinecone holds the searchable copy: one record
per chunk, id ``{document_id}#{position}``, in the user's namespace.
"""

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, UUIDPrimaryKeyMixin

# Document lifecycle: queued → extracting → chunking → indexing → verifying → ready (or failed)
DOC_ACTIVE_STATUSES = ("queued", "extracting", "chunking", "indexing", "verifying")
DOC_TERMINAL_STATUSES = ("ready", "failed")


class KnowledgeDocument(UUIDPrimaryKeyMixin, Base):
    """A file uploaded to a user's knowledge base."""

    __tablename__ = "knowledge_documents"

    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[str] = mapped_column(String(20), nullable=False)  # pdf, docx, md, txt
    size_bytes: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="queued")
    error: Mapped[str | None] = mapped_column(Text, default=None)
    page_count: Mapped[int | None] = mapped_column(Integer, default=None)
    char_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    token_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    chunk_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    indexed_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    embed_model: Mapped[str | None] = mapped_column(String(100), default=None)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    chunks: Mapped[list["KnowledgeChunk"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="KnowledgeChunk.position",
        lazy="noload",
    )

    def __repr__(self) -> str:
        return f"<KnowledgeDocument(id={self.id}, name={self.name!r}, status={self.status!r})>"


class KnowledgeChunk(UUIDPrimaryKeyMixin, Base):
    """One retrievable piece of a document (also stored as a Pinecone record)."""

    __tablename__ = "knowledge_chunks"

    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    heading: Mapped[str | None] = mapped_column(String(500), default=None)
    page: Mapped[int | None] = mapped_column(Integer, default=None)
    token_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="pending")  # pending, indexed
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    document: Mapped[KnowledgeDocument] = relationship(back_populates="chunks", lazy="noload")

    @property
    def record_id(self) -> str:
        """Pinecone record id for this chunk."""
        return f"{self.document_id}#{self.position}"

    def __repr__(self) -> str:
        return f"<KnowledgeChunk(document_id={self.document_id}, position={self.position})>"
