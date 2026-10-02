"""Pydantic response models for the HTTP API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SearchHit(BaseModel):
    document_id: int
    path: str
    title: str
    snippet: str
    title_highlighted: str
    score: float
    content_type: str = ""
    modified_at: str | None = None
    tags: list[str] = []


class SearchResponse(BaseModel):
    query: str
    total: int
    results: list[SearchHit]
    took_ms: float | None = None


class DocumentOut(BaseModel):
    id: int
    path: str
    title: str
    content_type: str
    file_size: int
    sha256: str
    simhash: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    word_count: int
    created_at: str | None = None
    modified_at: str | None = None
    indexed_at: str = ""
    tags: list[str] = []
    topics: list[str] = []


class DocumentList(BaseModel):
    total: int
    documents: list[DocumentOut]
    limit: int
    offset: int


class GraphNode(BaseModel):
    id: str
    kind: str
    label: str
    degree: int | None = None
    document_id: int | None = None
    path: str | None = None
    content_type: str | None = None
    word_count: int | None = None
    modified_at: str | None = None


class GraphEdge(BaseModel):
    source: str
    target: str
    kind: str
    weight: float | None = None


class GraphOut(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    meta: dict[str, Any] = Field(default_factory=dict)


class EventOut(BaseModel):
    id: int | None
    document_id: int | None
    path: str
    event_type: str
    title: str
    detail: str
    occurred_at: str


class TimelineOut(BaseModel):
    generated_at: str
    group_by: str
    buckets: list[dict[str, Any]]
    totals: dict[str, int]


class StatsOut(BaseModel):
    documents: int
    words: int
    bytes: int
    tags: int
    content_types: dict[str, int]
    events: int


class ScanResponse(BaseModel):
    created: int
    updated: int
    unchanged: int
    skipped: int
    errors: int
    removed: int = 0


class DuplicateGroupOut(BaseModel):
    kind: str
    primary_id: int
    document_ids: list[int]
    similarity: float | None = None


class DuplicatesResponse(BaseModel):
    exact: list[DuplicateGroupOut]
    similar: list[DuplicateGroupOut]


class TagOut(BaseModel):
    id: int
    name: str
    document_count: int


class HealthOut(BaseModel):
    status: str
    version: str
    documents: int
