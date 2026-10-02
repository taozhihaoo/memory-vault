"""Incremental scanning: index only what changed, delete what vanished."""

from __future__ import annotations

import hashlib
import threading
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from memoryvault.config import VaultConfig
from memoryvault.database.repository import DocumentRepository
from memoryvault.indexer.engine import IndexEngine, IndexResult, IndexStats

_CHUNK = 1 << 20


def file_sha256(path: Path) -> str:
    """Streamed SHA-256 so huge files never load into memory."""
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


class IncrementalScanner:
    """Full scans that re-index only files whose content actually changed.

    Change detection is two-stage: a cheap (size) probe first, then a SHA-256
    comparison for files whose size matches. Unchanged files are skipped
    without parsing.
    """

    def __init__(
        self,
        repo: DocumentRepository,
        engine: IndexEngine,
        config: VaultConfig | None = None,
    ) -> None:
        self.repo = repo
        self.engine = engine
        self.config = config or engine.config

    def scan(self, roots: list[Path] | Path | None = None) -> IndexStats:
        """Synchronize the database with the file system under *roots*."""
        if roots is None:
            roots = list(self.config.watch_paths)
        if isinstance(roots, (str, Path)):
            roots = [Path(roots)]
        roots = [Path(r) for r in roots]
        stats = IndexStats()
        seen_paths: set[str] = set()

        for root in roots:
            if not root.exists():
                continue
            for path in self.engine.discover_files(root):
                normalized = self.repo.normalize_path(path)
                seen_paths.add(normalized)
                if self._is_changed(path):
                    stats.add(self.engine.index_file(path))
                else:
                    stats.add(IndexResult(path=normalized, status="unchanged"))

        removed = self._remove_vanished(roots, seen_paths)
        stats.removed += removed
        return stats

    def _is_changed(self, path: Path) -> bool:
        """True when the file is new or its content hash differs from storage."""
        existing = self.repo.get_by_path(path)
        if existing is None:
            return True
        try:
            stat = path.stat()
        except OSError:
            return False
        if stat.st_size != existing.file_size:
            return True
        return file_sha256(path) != existing.sha256

    def _remove_vanished(self, roots: list[Path], seen: set[str]) -> int:
        """Mark documents deleted whose files disappeared from *roots*."""
        root_prefixes = [
            Path(r).resolve().as_posix() for r in roots if Path(r).exists()
        ]
        removed = 0
        for doc in self.repo.list_documents(limit=self.repo.count(), offset=0):
            in_roots = any(doc.path.startswith(prefix) for prefix in root_prefixes)
            if in_roots and doc.path not in seen:
                self.repo.mark_deleted(doc.id)  # type: ignore[arg-type]
                removed += 1
        return removed


class VaultWatcher:
    """Live file watcher: debounce events, then run an incremental pass.

    Built on watchdog, but the event callback (:meth:`_queue_event`) is
    trivial to invoke directly in tests without a real file system loop.
    """

    def __init__(
        self,
        scanner: IncrementalScanner,
        config: VaultConfig | None = None,
        *,
        on_scan=None,
    ) -> None:
        self.scanner = scanner
        self.config = config or scanner.config
        self.on_scan = on_scan  # optional callback(stats)
        self._lock = threading.Lock()
        self._pending: set[str] = set()
        self._timer: threading.Timer | None = None
        self._observer = None

    # ------------------------------------------------------------ lifecycle
    def start(self) -> None:
        observer = Observer()
        handler = self._make_handler()
        scheduled = False
        for root in self.config.watch_paths:
            root = Path(root)
            if root.exists():
                observer.schedule(handler, str(root), recursive=True)
                scheduled = True
        if scheduled:
            observer.start()
            self._observer = observer

    def stop(self) -> None:
        if self._observer is not None:
            self._observer.stop()
            self._observer.join(timeout=5)
            self._observer = None
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None

    def __enter__(self) -> "VaultWatcher":
        self.start()
        return self

    def __exit__(self, *exc_info) -> None:
        self.stop()

    # --------------------------------------------------------------- events
    def _make_handler(self) -> FileSystemEventHandler:
        watcher = self

        class _Handler(FileSystemEventHandler):
            def on_any_event(self, event):
                if event.is_directory:
                    return
                watcher._queue_event(getattr(event, "src_path", ""))

        return _Handler()

    def _queue_event(self, src_path: str) -> None:
        """Queue a changed path and (re)arm the debounce timer."""
        if not src_path:
            return
        if Path(src_path).suffix.lower().lstrip(".") not in self.config.extensions:
            return
        with self._lock:
            self._pending.add(src_path)
            if self._timer is None:
                self._timer = threading.Timer(
                    self.config.watcher_debounce_seconds, self._flush
                )
                self._timer.daemon = True
                self._timer.start()

    def _flush(self) -> None:
        with self._lock:
            paths = list(self._pending)
            self._pending.clear()
            self._timer = None
        if not paths:
            return
        # An incremental pass over the touched directories re-detects every
        # change by hash, so coalescing events per directory is always safe.
        roots = sorted({Path(p).parent for p in paths})
        stats = self.scanner.scan(roots=roots)
        if self.on_scan is not None:
            self.on_scan(stats)
