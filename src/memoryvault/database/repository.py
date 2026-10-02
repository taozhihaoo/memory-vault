"""Document repository: the single write path into the vault.

Every mutation goes through :class:`DocumentRepository` so that the main
tables, the FTS5 index, the tag tables, the SimHash band table and the event
log always stay consistent with each other.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

from memoryvault.textutil import count_words


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(slots=True)
class Document:
    """A stored document."""

    id: int | None = None
    path: str = ""
    title: str = ""
    content: str = ""
    content_type: str = ""
    file_size: int = 0
    sha256: str = ""
    simhash: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    word_count: int = 0
    created_at: str | None = None
    modified_at: str | None = None
    indexed_at: str = ""
    deleted: bool = False
    tags: list[str] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Document":
        try:
            metadata = json.loads(row["metadata"])
        except (TypeError, json.JSONDecodeError):
            metadata = {}
        return cls(
            id=row["id"],
            path=row["path"],
            title=row["title"],
            content=row["content"],
            content_type=row["content_type"],
            file_size=row["file_size"],
            sha256=row["sha256"],
            simhash=row["simhash"],
            metadata=metadata,
            word_count=row["word_count"],
            created_at=row["created_at"],
            modified_at=row["modified_at"],
            indexed_at=row["indexed_at"],
            deleted=bool(row["deleted"]),
        )

    def to_dict(self, *, include_content: bool = True, max_content: int | None = None) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": self.id,
            "path": self.path,
            "title": self.title,
            "content_type": self.content_type,
            "file_size": self.file_size,
            "sha256": self.sha256,
            "simhash": self.simhash,
            "metadata": self.metadata,
            "word_count": self.word_count,
            "created_at": self.created_at,
            "modified_at": self.modified_at,
            "indexed_at": self.indexed_at,
            "tags": self.tags,
            "topics": self.topics,
        }
        if include_content:
            content = self.content
            if max_content is not None:
                content = content[:max_content]
            data["content"] = content
        return data


@dataclass(slots=True)
class DocumentEvent:
    """One entry in the activity timeline."""

    id: int | None
    document_id: int | None
    path: str
    event_type: str  # created | updated | deleted | indexed
    title: str
    detail: str
    occurred_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "document_id": self.document_id,
            "path": self.path,
            "event_type": self.event_type,
            "title": self.title,
            "detail": self.detail,
            "occurred_at": self.occurred_at,
        }


class DocumentRepository:
    """CRUD + query operations over the documents table."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    # ------------------------------------------------------------- lookups
    def get(self, document_id: int, *, include_deleted: bool = False) -> Document | None:
        row = self.conn.execute(
            "SELECT * FROM documents WHERE id = ?", (document_id,)
        ).fetchone()
        if row is None or (row["deleted"] and not include_deleted):
            return None
        return self._load_with_terms(row)

    def get_by_path(self, path: str | Path, *, include_deleted: bool = False) -> Document | None:
        norm = self.normalize_path(path)
        row = self.conn.execute(
            "SELECT * FROM documents WHERE path = ?", (norm,)
        ).fetchone()
        if row is None or (row["deleted"] and not include_deleted):
            return None
        return self._load_with_terms(row)

    def get_content(self, document_id: int) -> str | None:
        row = self.conn.execute(
            "SELECT content FROM documents WHERE id = ?", (document_id,)
        ).fetchone()
        return row["content"] if row else None

    def list_documents(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        content_type: str | None = None,
        tag: str | None = None,
        include_deleted: bool = False,
    ) -> list[Document]:
        clauses: list[str] = []
        params: list[Any] = []
        if not include_deleted:
            clauses.append("d.deleted = 0")
        if content_type:
            clauses.append("d.content_type = ?")
            params.append(content_type)
        joins = ""
        if tag:
            joins = (
                " JOIN document_tags dt ON dt.document_id = d.id"
                " JOIN tags t ON t.id = dt.tag_id"
            )
            clauses.append("t.name = ?")
            params.append(tag)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        params.extend([limit, offset])
        rows = self.conn.execute(
            f"SELECT d.* FROM documents d{joins}{where}"
            " ORDER BY d.modified_at DESC NULLS LAST, d.id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        docs = [self._load_with_terms(row) for row in rows]
        return docs

    def _load_with_terms(self, row: sqlite3.Row) -> Document:
        doc = Document.from_row(row)
        doc.tags = self.tags_for(row["id"], source="tag")
        doc.topics = self.tags_for(row["id"], source="topic")
        return doc

    def count(
        self,
        *,
        include_deleted: bool = False,
        content_type: str | None = None,
        tag: str | None = None,
    ) -> int:
        clauses: list[str] = []
        params: list[Any] = []
        if not include_deleted:
            clauses.append("deleted = 0")
        joins = ""
        if content_type:
            clauses.append("content_type = ?")
            params.append(content_type)
        if tag:
            joins = (
                " JOIN document_tags dt ON dt.document_id = documents.id"
                " JOIN tags t ON t.id = dt.tag_id"
            )
            clauses.append("t.name = ?")
            params.append(tag)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        row = self.conn.execute(
            f"SELECT COUNT(*) AS n FROM documents{joins}{where}", params
        ).fetchone()
        return int(row["n"])

    def all_sha256(self) -> dict[str, list[int]]:
        """Map every content hash to *all* document ids sharing it."""
        rows = self.conn.execute(
            "SELECT id, sha256 FROM documents WHERE deleted = 0"
        ).fetchall()
        by_hash: dict[str, list[int]] = {}
        for r in rows:
            by_hash.setdefault(r["sha256"], []).append(r["id"])
        return by_hash

    def all_simhashes(self) -> dict[int, int]:
        rows = self.conn.execute(
            "SELECT id, simhash FROM documents WHERE deleted = 0 AND simhash IS NOT NULL"
        ).fetchall()
        return {r["id"]: int(r["simhash"], 16) for r in rows}

    @staticmethod
    def normalize_path(path: str | Path) -> str:
        return str(Path(path).resolve()).replace("\\", "/")

    # ---------------------------------------------------------------- tags
    def ensure_tag(self, name: str) -> int:
        name = name.strip().lower()
        if not name:
            raise ValueError("tag name must not be empty")
        row = self.conn.execute("SELECT id FROM tags WHERE name = ?", (name,)).fetchone()
        if row:
            return int(row["id"])
        cur = self.conn.execute("INSERT INTO tags (name) VALUES (?)", (name,))
        return int(cur.lastrowid)

    def set_tags(
        self, document_id: int, names: Iterable[str], *, source: str = "tag"
    ) -> None:
        names = [n.strip().lower() for n in names if n and n.strip()]
        self.conn.execute(
            "DELETE FROM document_tags WHERE document_id = ? AND source = ?",
            (document_id, source),
        )
        for name in dict.fromkeys(names):
            tag_id = self.ensure_tag(name)
            self.conn.execute(
                "INSERT OR IGNORE INTO document_tags (document_id, tag_id, source)"
                " VALUES (?, ?, ?)",
                (document_id, tag_id, source),
            )

    def tags_for(self, document_id: int, *, source: str | None = None) -> list[str]:
        sql = (
            "SELECT t.name FROM tags t JOIN document_tags dt ON dt.tag_id = t.id"
            " WHERE dt.document_id = ?"
        )
        params: list[Any] = [document_id]
        if source is not None:
            sql += " AND dt.source = ?"
            params.append(source)
        rows = self.conn.execute(sql + " ORDER BY t.name", params).fetchall()
        return [r["name"] for r in rows]

    def topics_for(self, document_id: int) -> list[str]:
        return self.tags_for(document_id, source="topic")

    def list_tags(self) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT t.id, t.name, COUNT(dt.document_id) AS document_count"
            " FROM tags t LEFT JOIN document_tags dt ON dt.tag_id = t.id"
            " GROUP BY t.id ORDER BY document_count DESC, t.name"
        ).fetchall()
        return [dict(r) for r in rows]

    # ---------------------------------------------------------------- events
    def add_event(
        self,
        *,
        document_id: int | None,
        path: str,
        event_type: str,
        title: str = "",
        detail: str = "",
        occurred_at: str | None = None,
    ) -> DocumentEvent:
        occurred_at = occurred_at or utc_now_iso()
        cur = self.conn.execute(
            "INSERT INTO document_events (document_id, path, event_type, title, detail,"
            " occurred_at) VALUES (?, ?, ?, ?, ?, ?)",
            (document_id, path, event_type, title, detail, occurred_at),
        )
        return DocumentEvent(
            id=int(cur.lastrowid),
            document_id=document_id,
            path=path,
            event_type=event_type,
            title=title,
            detail=detail,
            occurred_at=occurred_at,
        )

    def list_events(
        self,
        *,
        document_id: int | None = None,
        event_type: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[DocumentEvent]:
        clauses: list[str] = []
        params: list[Any] = []
        if document_id is not None:
            clauses.append("document_id = ?")
            params.append(document_id)
        if event_type:
            clauses.append("event_type = ?")
            params.append(event_type)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        params.extend([limit, offset])
        rows = self.conn.execute(
            "SELECT * FROM document_events" + where
            + " ORDER BY occurred_at DESC, id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        return [
            DocumentEvent(
                id=r["id"],
                document_id=r["document_id"],
                path=r["path"],
                event_type=r["event_type"],
                title=r["title"],
                detail=r["detail"],
                occurred_at=r["occurred_at"],
            )
            for r in rows
        ]

    def activity_histogram(self, days: int = 30) -> list[dict[str, Any]]:
        """Per-day event counts for the last *days* days."""
        rows = self.conn.execute(
            """
            SELECT substr(occurred_at, 1, 10) AS day, event_type, COUNT(*) AS n
            FROM document_events
            GROUP BY day, event_type
            ORDER BY day
            """
        ).fetchall()
        by_day: dict[str, dict[str, int]] = {}
        for r in rows:
            by_day.setdefault(r["day"], {})[r["event_type"]] = r["n"]
        out = [
            {"date": day, "counts": counts, "total": sum(counts.values())}
            for day, counts in sorted(by_day.items())
        ]
        return out[-days:]

    # --------------------------------------------------------- simhash bands
    def store_bands(self, document_id: int, simhash: int, bands: int = 4) -> None:
        self.conn.execute(
            "DELETE FROM simhash_bands WHERE document_id = ?", (document_id,)
        )
        width = 64 // bands
        for i in range(bands):
            band_value = (simhash >> (i * width)) & ((1 << width) - 1)
            self.conn.execute(
                "INSERT INTO simhash_bands (document_id, band_index, band_value)"
                " VALUES (?, ?, ?)",
                (document_id, i, band_value),
            )

    def band_candidates(
        self, simhash: int, bands: int = 4, *, exclude: set[int] = frozenset()
    ) -> set[int]:
        width = 64 // bands
        candidates: set[int] = set()
        for i in range(bands):
            band_value = (simhash >> (i * width)) & ((1 << width) - 1)
            rows = self.conn.execute(
                "SELECT document_id FROM simhash_bands"
                " WHERE band_index = ? AND band_value = ?",
                (i, band_value),
            ).fetchall()
            candidates.update(r["document_id"] for r in rows)
        candidates -= set(exclude)
        return candidates

    # ------------------------------------------------------------------ FTS
    def fts_replace(self, document_id: int, title: str, content: str) -> None:
        self.conn.execute("DELETE FROM documents_fts WHERE rowid = ?", (document_id,))
        self.conn.execute(
            "INSERT INTO documents_fts (rowid, title, content) VALUES (?, ?, ?)",
            (document_id, title, content),
        )

    def fts_delete(self, document_id: int) -> None:
        self.conn.execute("DELETE FROM documents_fts WHERE rowid = ?", (document_id,))

    def fts_count(self) -> int:
        row = self.conn.execute("SELECT COUNT(*) AS n FROM documents_fts").fetchone()
        return int(row["n"])

    # ---------------------------------------------------------------- writes
    def upsert(self, doc: Document) -> tuple[Document, str]:
        """Insert or update *doc*, returning ``(document, change)``.

        ``change`` is one of ``"created"``, ``"updated"`` or ``"unchanged"``.
        Unchanged documents (same sha256) are left untouched.
        """
        existing = self.get_by_path(doc.path, include_deleted=True)
        doc.path = self.normalize_path(doc.path)
        if existing and existing.sha256 == doc.sha256 and not existing.deleted:
            if doc.tags or doc.topics:
                if doc.tags:
                    self.set_tags(existing.id, doc.tags, source="tag")
                if doc.topics:
                    self.set_tags(existing.id, doc.topics, source="topic")
                self.conn.commit()
            return existing, "unchanged"

        if doc.indexed_at == "":
            doc.indexed_at = utc_now_iso()
        if not doc.word_count:
            doc.word_count = count_words(doc.content)

        if existing is None:
            cur = self.conn.execute(
                """
                INSERT INTO documents (path, title, content, content_type, file_size,
                    sha256, simhash, metadata, word_count, created_at, modified_at,
                    indexed_at, deleted)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                """,
                (
                    doc.path, doc.title, doc.content, doc.content_type, doc.file_size,
                    doc.sha256, doc.simhash, json.dumps(doc.metadata, ensure_ascii=False),
                    doc.word_count, doc.created_at, doc.modified_at, doc.indexed_at,
                ),
            )
            doc.id = int(cur.lastrowid)
            change = "created"
        else:
            doc.id = existing.id
            doc.created_at = doc.created_at or existing.created_at
            self.conn.execute(
                """
                UPDATE documents SET title=?, content=?, content_type=?, file_size=?,
                    sha256=?, simhash=?, metadata=?, word_count=?, created_at=?,
                    modified_at=?, indexed_at=?, deleted=0
                WHERE id = ?
                """,
                (
                    doc.title, doc.content, doc.content_type, doc.file_size,
                    doc.sha256, doc.simhash, json.dumps(doc.metadata, ensure_ascii=False),
                    doc.word_count, doc.created_at, doc.modified_at, doc.indexed_at,
                    doc.id,
                ),
            )
            change = "updated"

        assert doc.id is not None
        self.fts_replace(doc.id, doc.title, doc.content)
        if doc.simhash is not None:
            self.store_bands(doc.id, int(doc.simhash, 16))
        if doc.tags:
            self.set_tags(doc.id, doc.tags, source="tag")
        if doc.topics:
            self.set_tags(doc.id, doc.topics, source="topic")
        self.add_event(
            document_id=doc.id,
            path=doc.path,
            event_type=change,
            title=doc.title,
            detail=f"{doc.content_type}, {doc.word_count} words",
        )
        self.conn.commit()
        return doc, change

    def mark_deleted(self, document_id: int) -> None:
        row = self.conn.execute(
            "SELECT path, title FROM documents WHERE id = ?", (document_id,)
        ).fetchone()
        if row is None:
            return
        self.conn.execute(
            "UPDATE documents SET deleted = 1 WHERE id = ?", (document_id,)
        )
        self.fts_delete(document_id)
        self.add_event(
            document_id=document_id,
            path=row["path"],
            event_type="deleted",
            title=row["title"],
        )
        self.conn.commit()

    def purge_deleted(self) -> int:
        rows = self.conn.execute(
            "SELECT id FROM documents WHERE deleted = 1"
        ).fetchall()
        for r in rows:
            self.conn.execute("DELETE FROM documents WHERE id = ?", (r["id"],))
        self.conn.commit()
        return len(rows)

    def set_setting(self, key: str, value: str) -> None:
        self.conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?)"
            " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
        self.conn.commit()

    def get_setting(self, key: str) -> str | None:
        row = self.conn.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else None

    def stats(self) -> dict[str, Any]:
        """Vault-wide statistics for the dashboard."""
        row = self.conn.execute(
            """
            SELECT COUNT(*) AS documents,
                   COALESCE(SUM(word_count), 0) AS words,
                   COALESCE(SUM(file_size), 0) AS bytes
            FROM documents WHERE deleted = 0
            """
        ).fetchone()
        ctypes = self.conn.execute(
            "SELECT content_type, COUNT(*) AS n FROM documents WHERE deleted = 0"
            " GROUP BY content_type ORDER BY n DESC"
        ).fetchall()
        return {
            "documents": int(row["documents"]),
            "words": int(row["words"]),
            "bytes": int(row["bytes"]),
            "tags": len(self.list_tags()),
            "content_types": {r["content_type"] or "unknown": r["n"] for r in ctypes},
            "events": self.conn.execute(
                "SELECT COUNT(*) AS n FROM document_events"
            ).fetchone()["n"],
        }


def _in_clause(values: Sequence[str]) -> str:
    return ",".join("?" for _ in values)
