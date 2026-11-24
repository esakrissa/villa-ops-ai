"""Pydantic schemas for the knowledge base API."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class KnowledgeChunkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    position: int
    text: str
    heading: str | None
    page: int | None
    token_count: int
    status: str


class KnowledgeDocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    file_type: str
    size_bytes: int
    status: str
    error: str | None
    page_count: int | None
    char_count: int
    token_count: int
    chunk_count: int
    indexed_count: int
    embed_model: str | None
    created_at: datetime
    updated_at: datetime


class KnowledgeDocumentDetail(KnowledgeDocumentResponse):
    chunks: list[KnowledgeChunkResponse]


class KnowledgeDocumentList(BaseModel):
    items: list[KnowledgeDocumentResponse]
    total: int


class KnowledgeStatus(BaseModel):
    enabled: bool
    index: str
    embed_model: str
    rerank_model: str | None
    max_upload_mb: int
    supported_types: list[str]
    chunk_tokens: int
    overlap_tokens: int


class KnowledgeSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    top_k: int = Field(default=5, ge=1, le=10)
    rerank: bool = True


class KnowledgeSearchResult(BaseModel):
    document: str
    document_id: str
    section: str | None
    page: int | None
    chunk: int
    score: float
    text: str


class KnowledgeSearchResponse(BaseModel):
    query: str
    results: list[KnowledgeSearchResult]
    total: int
    reranked: bool
    latency_ms: int
