"""Runtime configuration for a MemoryVault instance."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_EXCLUDED_DIRS = {
    ".git", ".hg", ".svn", "__pycache__", "node_modules",
    ".venv", "venv", ".idea", ".vscode", ".memoryvault",
}

DEFAULT_EXCLUDED_FILES = {".DS_Store", "Thumbs.db", "desktop.ini"}


def _default_home() -> Path:
    env = os.environ.get("MEMORYVAULT_HOME")
    if env:
        return Path(env)
    return Path.home() / ".memoryvault"


@dataclass
class VaultConfig:
    """Configuration for one MemoryVault vault.

    A *vault* is a single SQLite database plus the set of directories that
    are indexed into it. Everything is stored locally; no network access
    happens anywhere in the core.
    """

    #: Path of the SQLite database file.
    db_path: Path = field(default_factory=lambda: _default_home() / "memoryvault.db")

    #: Directories watched and indexed by the incremental scanner.
    watch_paths: list[Path] = field(default_factory=list)

    #: File extensions that are indexed (without dot, lowercase).
    extensions: frozenset[str] = frozenset(
        {"txt", "md", "markdown", "pdf", "docx", "html", "htm", "json", "csv"}
    )

    #: Directory names that are never entered during scanning.
    excluded_dirs: set[str] = field(default_factory=lambda: set(DEFAULT_EXCLUDED_DIRS))

    #: File names that are never indexed.
    excluded_files: set[str] = field(default_factory=lambda: set(DEFAULT_EXCLUDED_FILES))

    #: Files larger than this (bytes) are skipped.
    max_file_size: int = 64 * 1024 * 1024

    #: Hamming-distance threshold under which two SimHashes count as
    #: near-duplicates.
    simhash_threshold: int = 12

    #: Maximum number of keyword topics extracted per document for the graph.
    topics_per_document: int = 8

    #: Tag co-occurrence edges are computed for the top-N tags only.
    max_cooccurrence_tags: int = 30

    #: Seconds to wait for file-system events to settle before re-indexing.
    watcher_debounce_seconds: float = 1.0

    #: Host/port for the API server.
    api_host: str = "127.0.0.1"
    api_port: int = 8000

    #: Directory containing an optional built frontend (frontend/dist).
    frontend_dist: Path | None = None

    def __post_init__(self) -> None:
        self.db_path = Path(self.db_path)
        self.watch_paths = [Path(p) for p in self.watch_paths]
        if isinstance(self.extensions, (list, tuple, set)) and not isinstance(
            self.extensions, frozenset
        ):
            self.extensions = frozenset(self.extensions)
        self.extensions = frozenset(e.lower().lstrip(".") for e in self.extensions)
        self.frontend_dist = Path(self.frontend_dist) if self.frontend_dist else None

    def resolve(self) -> "VaultConfig":
        """Return a copy with relative paths anchored to the current directory."""
        cfg = VaultConfig(
            db_path=self.db_path.expanduser(),
            watch_paths=self.watch_paths,
            extensions=self.extensions,
            excluded_dirs=set(self.excluded_dirs),
            excluded_files=set(self.excluded_files),
            max_file_size=self.max_file_size,
            simhash_threshold=self.simhash_threshold,
            topics_per_document=self.topics_per_document,
            max_cooccurrence_tags=self.max_cooccurrence_tags,
            watcher_debounce_seconds=self.watcher_debounce_seconds,
            api_host=self.api_host,
            api_port=self.api_port,
            frontend_dist=self.frontend_dist,
        )
        cfg.db_path = cfg.db_path.expanduser()
        cfg.watch_paths = [p.expanduser() for p in cfg.watch_paths]
        return cfg

    def is_indexable(self, path: Path) -> bool:
        """Return True when *path* should be indexed under this config."""
        name = path.name
        if name in self.excluded_files or name.startswith("~$"):
            return False
        if path.suffix.lower().lstrip(".") not in self.extensions:
            return False
        return not any(part in self.excluded_dirs for part in path.parts)
