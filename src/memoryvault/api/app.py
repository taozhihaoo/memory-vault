"""FastAPI application factory."""

from __future__ import annotations

import os
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from memoryvault import __version__
from memoryvault.api.schemas import (
    DocumentList,
    DocumentOut,
    DuplicatesResponse,
    DuplicateGroupOut,
    GraphOut,
    HealthOut,
    ScanResponse,
    SearchHit,
    SearchResponse,
    StatsOut,
    TagOut,
    TimelineOut,
)
from memoryvault.config import VaultConfig
from memoryvault.database.repository import Document
from memoryvault.vault import Vault


def create_app(
    vault: Vault | None = None,
    config: VaultConfig | None = None,
) -> FastAPI:
    """Build the API around an existing :class:`Vault` (or create one)."""
    owned = vault is None
    cfg = (vault.config if vault else config or VaultConfig()).resolve()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.vault = vault or Vault(cfg)
        yield
        if owned:
            app.state.vault.close()

    app = FastAPI(
        title="MemoryVault API",
        description=(
            "Local-first personal knowledge engine. "
            "Fully offline: every endpoint reads from the local SQLite vault."
        ),
        version=__version__,
        lifespan=lifespan,
    )
    # The API is bound to loopback and holds the user's private documents.
    # ``allow_origins=["*"]`` let *any* website in the browser read the whole
    # vault; restrict cross-origin access to local dev origins (or an
    # explicit allow-list) instead.
    extra_origins = [
        origin.strip()
        for origin in os.environ.get("MEMORYVAULT_CORS_ORIGINS", "").split(",")
        if origin.strip()
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=extra_origins,
        allow_origin_regex=(
            None if extra_origins else
            r"^https?://(localhost|127\.0\.0\.1|\[::1\])(:\d+)?$"
        ),
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type"],
    )

    def get_vault() -> Vault:
        return app.state.vault

    # ------------------------------------------------------------------ system
    @app.get("/api/health", response_model=HealthOut, tags=["system"])
    def health(v: Vault = Depends(get_vault)):
        return HealthOut(
            status="ok", version=__version__, documents=v.repo.count()
        )

    @app.get("/api/stats", response_model=StatsOut, tags=["system"])
    def stats(v: Vault = Depends(get_vault)):
        return StatsOut(**v.stats())

    @app.post("/api/scan", response_model=ScanResponse, tags=["system"])
    def scan(
        roots: list[str] | None = None,
        v: Vault = Depends(get_vault),
    ):
        """Run an incremental scan.

        With no body, use configured watch paths or the directories recorded
        by previous indexing runs — so re-scanning works for a vault created
        with ``memoryvault index <dir>``.
        """
        paths = [Path(r) for r in roots] if roots else None
        if paths:
            v.scanner.remember_roots(paths)
        result = v.scanner.scan(roots=paths)
        return ScanResponse(**result.to_dict())

    # --------------------------------------------------------------- documents
    @app.get("/api/documents", response_model=DocumentList, tags=["documents"])
    def list_documents(
        limit: int = Query(50, ge=1, le=500),
        offset: int = Query(0, ge=0),
        content_type: str | None = None,
        tag: str | None = None,
        v: Vault = Depends(get_vault),
    ):
        total = v.repo.count(content_type=content_type, tag=tag)
        docs = v.repo.list_documents(
            limit=limit, offset=offset, content_type=content_type, tag=tag
        )
        return DocumentList(
            total=total, documents=[_doc_out(d) for d in docs],
            limit=limit, offset=offset,
        )

    @app.get("/api/documents/{document_id}", response_model=DocumentOut, tags=["documents"])
    def get_document(document_id: int, v: Vault = Depends(get_vault)):
        doc = v.repo.get(document_id)
        if doc is None:
            raise HTTPException(404, "document not found")
        return _doc_out(doc)

    @app.get("/api/documents/{document_id}/content", tags=["documents"])
    def get_document_content(
        document_id: int,
        v: Vault = Depends(get_vault),
        max_chars: int | None = Query(None, ge=1),
    ):
        content = v.repo.get_content(document_id)
        if content is None:
            raise HTTPException(404, "document not found")
        if max_chars is not None:
            content = content[:max_chars]
        return {"document_id": document_id, "content": content}

    @app.get("/api/documents/{document_id}/history", tags=["timeline"])
    def get_document_history(document_id: int, v: Vault = Depends(get_vault)):
        if v.repo.get(document_id, include_deleted=True) is None:
            raise HTTPException(404, "document not found")
        return {"document_id": document_id, "events": v.timeline.document_history(document_id)}

    @app.get("/api/documents/{document_id}/related", response_model=SearchResponse, tags=["documents"])
    def related_documents(
        document_id: int, limit: int = Query(5, ge=1, le=50), v: Vault = Depends(get_vault)
    ):
        found = v.search.more_like(document_id, limit=limit)
        return SearchResponse(
            query=f"related:{document_id}",
            total=len(found),
            results=[SearchHit(**h.to_dict()) for h in found],
        )

    @app.get("/api/documents/{document_id}/similar", tags=["documents"])
    def similar_documents(
        document_id: int, limit: int = Query(10, ge=1, le=50), v: Vault = Depends(get_vault)
    ):
        return {"document_id": document_id, "similar": v.dedup.similar_to(document_id, limit=limit)}

    @app.get("/api/tags", response_model=list[TagOut], tags=["documents"])
    def list_tags(v: Vault = Depends(get_vault)):
        return [TagOut(**t) for t in v.repo.list_tags()]

    # ------------------------------------------------------------------ search
    @app.get("/api/search", response_model=SearchResponse, tags=["search"])
    def search(
        q: str = Query(..., min_length=1, description="Keyword query"),
        limit: int = Query(20, ge=1, le=100),
        offset: int = Query(0, ge=0),
        content_type: str | None = None,
        tag: str | None = None,
        v: Vault = Depends(get_vault),
    ):
        started = time.perf_counter()
        found = v.search.search(
            q, limit=limit, offset=offset, content_type=content_type, tag=tag
        )
        took = (time.perf_counter() - started) * 1000
        return SearchResponse(
            query=found["query"],
            total=found["total"],
            results=[SearchHit(**h.to_dict()) for h in found["results"]],
            took_ms=round(took, 2),
        )

    @app.get("/api/suggest", tags=["search"])
    def suggest(
        q: str = Query(..., min_length=1),
        limit: int = Query(10, ge=1, le=50),
        v: Vault = Depends(get_vault),
    ):
        return {"prefix": q, "suggestions": v.search.suggest(q, limit=limit)}

    # ------------------------------------------------------------------- graph
    @app.get("/api/graph", response_model=GraphOut, tags=["graph"])
    def graph(
        include_similar: bool = True,
        include_cooccurrence: bool = True,
        limit: int | None = Query(None, ge=1),
        v: Vault = Depends(get_vault),
    ):
        return v.graph.build(
            include_similar=include_similar,
            include_cooccurrence=include_cooccurrence,
            limit=limit,
        )

    @app.get("/api/graph/neighborhood/{document_id}", response_model=GraphOut, tags=["graph"])
    def graph_neighborhood(
        document_id: int, depth: int = Query(1, ge=1, le=4), v: Vault = Depends(get_vault)
    ):
        if v.repo.get(document_id) is None:
            raise HTTPException(404, "document not found")
        return v.graph.neighborhood(document_id, depth=depth)

    # ---------------------------------------------------------------- timeline
    @app.get("/api/timeline", response_model=TimelineOut, tags=["timeline"])
    def timeline(
        days: int = Query(90, ge=1, le=3650),
        group_by: str = Query("day", pattern="^(day|month)$"),
        v: Vault = Depends(get_vault),
    ):
        return TimelineOut(**v.timeline.activity(days=days, group_by=group_by))

    @app.get("/api/timeline/events", tags=["timeline"])
    def timeline_events(
        limit: int = Query(50, ge=1, le=500),
        offset: int = Query(0, ge=0),
        event_type: str | None = None,
        v: Vault = Depends(get_vault),
    ):
        events = v.repo.list_events(limit=limit, offset=offset, event_type=event_type)
        return {
            "total": v.repo.count_events(event_type=event_type),
            "events": [e.to_dict() for e in events],
        }

    # -------------------------------------------------------------- duplicates
    @app.get("/api/duplicates", response_model=DuplicatesResponse, tags=["duplicates"])
    def duplicates(v: Vault = Depends(get_vault)):
        found = v.dedup.find_all()
        return DuplicatesResponse(
            exact=[DuplicateGroupOut(**g.to_dict()) for g in found["exact"]],
            similar=[DuplicateGroupOut(**g.to_dict()) for g in found["similar"]],
        )

    # ---------------------------------------------------------------- frontend
    frontend_dist = cfg.frontend_dist
    if frontend_dist and Path(frontend_dist).is_dir():
        _mount_frontend(app, Path(frontend_dist))

    return app


def _doc_out(doc: Document) -> DocumentOut:
    return DocumentOut(
        id=doc.id,  # type: ignore[arg-type]
        path=doc.path,
        title=doc.title,
        content_type=doc.content_type,
        file_size=doc.file_size,
        sha256=doc.sha256,
        simhash=doc.simhash,
        metadata=doc.metadata,
        word_count=doc.word_count,
        created_at=doc.created_at,
        modified_at=doc.modified_at,
        indexed_at=doc.indexed_at,
        tags=doc.tags,
        topics=doc.topics,
    )


def _mount_frontend(app: FastAPI, dist: Path) -> None:
    """Serve the built React dashboard as static files (SPA fallback)."""
    dist = dist.resolve()
    assets = dist / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    def _safe_static(relative: str) -> Path | None:
        """Resolve *relative* inside *dist*, rejecting traversal attempts."""
        if not relative or "\x00" in relative:
            return None
        try:
            candidate = (dist / relative).resolve()
            candidate.relative_to(dist)
        except (ValueError, OSError):
            return None
        return candidate if candidate.is_file() else None

    @app.get("/", include_in_schema=False)
    def index():  # pragma: no cover - static passthrough
        return FileResponse(dist / "index.html")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa_fallback(full_path: str):  # pragma: no cover - static passthrough
        # Unknown API routes must be JSON 404s, not the SPA shell (which used
        # to make a typo look like a successful request).
        if full_path == "api" or full_path.startswith("api/"):
            raise HTTPException(404, "not found")
        candidate = _safe_static(full_path)
        if candidate is not None:
            return FileResponse(candidate)
        return FileResponse(dist / "index.html")
