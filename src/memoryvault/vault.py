"""Vault: one object that wires every MemoryVault subsystem together."""

from __future__ import annotations

from pathlib import Path

from memoryvault.config import VaultConfig
from memoryvault.database.connection import connect
from memoryvault.database.repository import DocumentRepository
from memoryvault.dedup import DuplicateDetector
from memoryvault.indexer.engine import IndexEngine, IndexStats
from memoryvault.indexer.scanner import IncrementalScanner
from memoryvault.graph.builder import GraphBuilder
from memoryvault.search.engine import SearchEngine
from memoryvault.timeline.service import TimelineService


class Vault:
    """Facade over config, database, indexing, search, graph and timeline.

    Example::

        vault = Vault.open("my-vault.db")
        vault.engine.index_directory("notes/")
        hits = vault.search.search("project")
    """

    def __init__(self, config: VaultConfig | None = None) -> None:
        self.config = (config or VaultConfig()).resolve()
        self.conn = connect(self.config.db_path)
        self.repo = DocumentRepository(self.conn)
        self.engine = IndexEngine(self.repo, self.config)
        self.scanner = IncrementalScanner(self.repo, self.engine, self.config)
        self.search = SearchEngine(self.repo)
        self.graph = GraphBuilder(self.repo, self.config)
        self.timeline = TimelineService(self.repo)
        self.dedup = DuplicateDetector(self.repo, threshold=self.config.simhash_threshold)

    @classmethod
    def open(cls, db_path: str | Path, **config_kwargs) -> "Vault":
        cfg = VaultConfig(db_path=Path(db_path), **config_kwargs)
        return cls(cfg)

    @classmethod
    def in_memory(cls, **config_kwargs) -> "Vault":
        """A throwaway vault backed by an in-memory database (tests/demos)."""
        cfg = VaultConfig(db_path=":memory:", **config_kwargs)
        return cls(cfg)

    # -------------------------------------------------------------- operations
    def index(self, root: str | Path) -> IndexStats:
        """Index a directory tree (thin wrapper over :attr:`engine`)."""
        return self.engine.index_directory(Path(root))

    def stats(self) -> dict:
        return self.repo.stats()

    def close(self) -> None:
        try:
            self.conn.close()
        except Exception:  # pragma: no cover - defensive
            pass

    def __enter__(self) -> "Vault":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()
