"""File watcher tests (debounce logic, no real OS event loop needed)."""

from __future__ import annotations

import time
from pathlib import Path

from memoryvault.config import VaultConfig
from memoryvault.indexer.scanner import VaultWatcher


class _Recorder:
    def __init__(self) -> None:
        self.runs: list = []

    def __call__(self, stats) -> None:
        self.runs.append(stats)


def _watcher(vault, recorder) -> VaultWatcher:
    cfg = VaultConfig(
        watch_paths=vault.config.watch_paths,
        watcher_debounce_seconds=0.05,
    )
    cfg.db_path = vault.config.db_path
    return VaultWatcher(vault.scanner, cfg, on_scan=recorder)


def test_watcher_flush_indexes_changed_files(vault, docs_dir: Path):
    vault.index(docs_dir)
    (docs_dir / "minutes.txt").write_text("Meeting minutes\n\nWatcher edited this.\n",
                                          encoding="utf-8")
    recorder = _Recorder()
    watcher = _watcher(vault, recorder)
    watcher._queue_event(str(docs_dir / "minutes.txt"))
    deadline = time.time() + 5
    while not recorder.runs and time.time() < deadline:
        time.sleep(0.01)
    assert recorder.runs, "debounced flush never ran"
    assert recorder.runs[0].updated == 1


def test_watcher_ignores_unrelated_extensions(vault, docs_dir: Path):
    recorder = _Recorder()
    watcher = _watcher(vault, recorder)
    watcher._queue_event(str(docs_dir / "ignored.xyz"))
    time.sleep(0.3)
    assert not recorder.runs
    watcher.stop()


def test_watcher_coalesces_events_into_one_scan(vault, docs_dir: Path):
    vault.index(docs_dir)
    (docs_dir / "a-change.md").write_text("# A\n\ntouched by watcher", encoding="utf-8")
    recorder = _Recorder()
    watcher = _watcher(vault, recorder)
    watcher._queue_event(str(docs_dir / "a-change.md"))
    watcher._queue_event(str(docs_dir / "a-change.md"))
    watcher._queue_event(str(docs_dir / "a-change.md"))
    deadline = time.time() + 5
    while not recorder.runs and time.time() < deadline:
        time.sleep(0.01)
    assert len(recorder.runs) == 1  # debounce collapsed the burst


def test_watcher_ignores_empty_paths(vault):
    recorder = _Recorder()
    watcher = _watcher(vault, recorder)
    watcher._queue_event("")
    time.sleep(0.2)
    assert not recorder.runs
    watcher.stop()


def test_watcher_context_manager_starts_and_stops(vault, docs_dir: Path):
    import contextlib

    cfg = VaultConfig(watch_paths=[docs_dir])
    watcher = VaultWatcher(vault.scanner, cfg)
    with contextlib.suppress(Exception):
        with watcher:
            assert watcher._observer is not None
    assert watcher._observer is None
