"""The indexing engine ties parsers, hashing, SimHash and storage together."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterable

from memoryvault.config import VaultConfig
from memoryvault.database.repository import Document, DocumentRepository
from memoryvault.dedup.simhash import SimHash
from memoryvault.keywords import extract_keywords
from memoryvault.parser import ParsingError, parse_file


@dataclass(slots=True)
class IndexResult:
    """Outcome of indexing a single file."""

    path: str
    status: str  # created | updated | unchanged | skipped | error
    document_id: int | None = None
    error: str | None = None


@dataclass(slots=True)
class IndexStats:
    """Aggregate outcome of an indexing run."""

    created: int = 0
    updated: int = 0
    unchanged: int = 0
    skipped: int = 0
    errors: int = 0
    removed: int = 0
    results: list[IndexResult] = field(default_factory=list)

    _FIELD_FOR_STATUS = {
        "created": "created",
        "updated": "updated",
        "unchanged": "unchanged",
        "skipped": "skipped",
        "error": "errors",
    }

    def add(self, result: IndexResult) -> None:
        field_name = self._FIELD_FOR_STATUS.get(result.status)
        if field_name is not None:
            setattr(self, field_name, getattr(self, field_name) + 1)
        self.results.append(result)

    def to_dict(self) -> dict:
        return {
            "created": self.created,
            "updated": self.updated,
            "unchanged": self.unchanged,
            "skipped": self.skipped,
            "errors": self.errors,
            "removed": self.removed,
        }


class IndexEngine:
    """Indexes individual files or whole directory trees into the vault."""

    def __init__(self, repo: DocumentRepository, config: VaultConfig | None = None) -> None:
        self.repo = repo
        # The config instance is shared by reference so runtime changes
        # (e.g. new watch paths) are visible to every Vault subsystem.
        self.config = config or VaultConfig()
        self.simhash = SimHash()

    # ------------------------------------------------------------ single file
    def index_file(self, path: Path) -> IndexResult:
        """Parse and index one file. Only changed files touch the database."""
        path = Path(path)
        if not self.config.is_indexable(path):
            return IndexResult(path=str(path), status="skipped")
        try:
            stat = path.stat()
        except OSError as exc:
            return IndexResult(path=str(path), status="error", error=str(exc))
        if stat.st_size > self.config.max_file_size:
            return IndexResult(path=str(path), status="skipped")

        try:
            parsed = parse_file(path)
        except ParsingError as exc:
            return IndexResult(path=str(path), status="error", error=str(exc))

        raw = path.read_bytes()
        sha256 = self.simhash_sha(raw)
        fingerprint = self.simhash.fingerprint(parsed.content)

        tags = self.collect_tags(parsed, path)
        topics = extract_keywords(
            parsed.content, limit=self.config.topics_per_document
        )

        doc = Document(
            path=str(path.resolve()),
            title=parsed.title,
            content=parsed.content,
            content_type=self.content_type_for(path),
            file_size=stat.st_size,
            sha256=sha256,
            simhash=SimHash.to_hex(fingerprint),
            metadata=parsed.metadata,
            word_count=parsed.word_count,
            created_at=self.to_iso(parsed.created_at),
            modified_at=self.to_iso(parsed.modified_at),
            tags=sorted(set(tags)),
            topics=topics,
        )
        stored, change = self.repo.upsert(doc)
        return IndexResult(
            path=doc.path, status=change, document_id=stored.id
        )

    # ---------------------------------------------------------------- batch
    def index_directory(
        self, root: Path, *, recursive: bool = True
    ) -> IndexStats:
        """Index every supported file under *root*."""
        stats = IndexStats()
        root = Path(root)
        if not root.exists():
            return stats
        paths = self.discover_files(root, recursive=recursive)
        for path in paths:
            stats.add(self.index_file(path))
        self.remove_missing(root)
        return stats

    def discover_files(self, root: Path, *, recursive: bool = True) -> list[Path]:
        """All indexable files under *root*, deterministic order."""
        root = Path(root)
        if root.is_file():
            return [root] if self.config.is_indexable(root) else []
        files: list[Path] = []
        iterator = root.rglob("*") if recursive else root.glob("*")
        for path in sorted(iterator):
            if path.is_file() and self.is_enterable(path):
                if self.config.is_indexable(path):
                    files.append(path)
        return files

    def is_enterable(self, path: Path) -> bool:
        return not any(part in self.config.excluded_dirs for part in path.parts)

    def remove_missing(self, roots: Path | Iterable[Path]) -> int:
        """Mark stored documents whose files no longer exist as deleted."""
        if isinstance(roots, (str, Path)):
            roots = [Path(roots)]
        root_list = [Path(r).resolve() for r in roots]
        removed = 0
        for doc in self.repo.list_documents(limit=self.repo.count(), offset=0):
            if not any(doc.path.startswith(r.as_posix()) for r in root_list):
                continue
            if not Path(doc.path).exists():
                self.repo.mark_deleted(doc.id)  # type: ignore[arg-type]
                removed += 1
        return removed

    # ------------------------------------------------------------- helpers
    def collect_tags(self, parsed, path: Path) -> list[str]:
        """Tags from frontmatter/metadata; extension as a coarse tag too."""
        tags: list[str] = []
        meta_tags = parsed.metadata.get("tags") or []
        if isinstance(meta_tags, str):
            meta_tags = [meta_tags]
        for tag in meta_tags:
            tag = str(tag).strip().strip("#").lower()
            if tag and len(tag) <= 64:
                tags.append(tag)
        category = parsed.metadata.get("category")
        if isinstance(category, str) and category.strip():
            tags.append(category.strip().lower())
        return tags

    def content_type_for(self, path: Path) -> str:
        from memoryvault.parser import get_parser

        try:
            return get_parser(path).content_type
        except ParsingError:
            return "unknown"

    @staticmethod
    def simhash_sha(raw: bytes) -> str:
        import hashlib

        return hashlib.sha256(raw).hexdigest()

    @staticmethod
    def to_iso(value: datetime | None) -> str | None:
        if value is None:
            return None
        if value.tzinfo is not None:
            value = value.astimezone()
        return value.isoformat(timespec="seconds")
