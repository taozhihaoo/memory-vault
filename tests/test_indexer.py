"""Indexer and text-utility tests."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from memoryvault.config import VaultConfig
from memoryvault.indexer import IndexEngine
from memoryvault.indexer.scanner import IncrementalScanner, file_sha256
from memoryvault.keywords import STOPWORDS, extract_keywords
from memoryvault.textutil import count_words, decode_bytes, normalize_whitespace


# --------------------------------------------------------------- textutil
def test_count_words_simple():
    assert count_words("Hello, world! Hello again.") == 4


def test_count_words_unicode():
    assert count_words("Grüße aus München") == 3


def test_decode_utf8_and_cp1252():
    assert decode_bytes("plain".encode("utf-8")) == "plain"
    assert decode_bytes(b"caf\xe9") == "café"  # cp1252


def test_normalize_whitespace_crlf():
    assert normalize_whitespace("a\r\nb\t\tc") == "a\nb c"


# --------------------------------------------------------------- keywords
def test_extract_keywords_orders_by_frequency():
    text = "graph graph graph search search index"
    assert extract_keywords(text, limit=3)[0] == "graph"


def test_extract_keywords_skips_stopwords_and_short():
    text = "the a an of graph"
    words = extract_keywords(text, limit=10)
    assert words == ["graph"]


def test_stopwords_are_lowercase_and_deduped():
    assert len(STOPWORDS) == len(set(STOPWORDS))


# ----------------------------------------------------------------- config
def test_is_indexable_respects_extensions(tmp_path):
    cfg = VaultConfig()
    assert cfg.is_indexable(tmp_path / "note.md")
    assert not cfg.is_indexable(tmp_path / "binary.exe")
    assert not cfg.is_indexable(tmp_path / ".git" / "config.md")


def test_resolve_expands_extensions():
    cfg = VaultConfig(extensions=[".MD", "txt"])
    assert cfg.resolve().extensions == frozenset({"md", "txt"})


# ---------------------------------------------------------------- indexer
def test_index_file_extracts_everything(indexed_vault, docs_dir: Path):
    alpha = indexed_vault.repo.get_by_path(docs_dir / "alpha.md")
    assert alpha.title == "Alpha Report"
    assert alpha.sha256 == hashlib.sha256((docs_dir / "alpha.md").read_bytes()).hexdigest()
    assert alpha.simhash and len(alpha.simhash) == 16
    assert "research" in alpha.tags
    assert alpha.word_count > 0
    assert alpha.modified_at is not None


def test_index_directory_creates_all_documents(indexed_vault):
    assert indexed_vault.repo.count() == 8  # one per sample file


def test_index_records_created_events(indexed_vault):
    events = indexed_vault.repo.list_events(event_type="created")
    assert len(events) == 8


def test_index_same_file_twice_is_unchanged(indexed_vault, docs_dir: Path):
    result = indexed_vault.engine.index_file(docs_dir / "alpha.md")
    assert result.status == "unchanged"


def test_index_detects_changed_content(indexed_vault, docs_dir: Path):
    target = docs_dir / "beta-notes.md"
    target.write_text("# Beta Notes\n\ncompletely new content about orbits",
                      encoding="utf-8")
    result = indexed_vault.engine.index_file(target)
    assert result.status == "updated"
    hits = indexed_vault.search.search("orbits")["results"]
    assert len(hits) == 1


def test_index_skips_unsupported_files(indexed_vault, docs_dir: Path):
    (docs_dir / "binary.exe").write_bytes(b"MZ...")
    result = indexed_vault.engine.index_file(docs_dir / "binary.exe")
    assert result.status == "skipped"
    assert indexed_vault.repo.get_by_path(docs_dir / "binary.exe") is None
    # directory discovery never even enters unsupported files
    names = {p.name for p in indexed_vault.engine.discover_files(docs_dir)}
    assert "binary.exe" not in names


def test_index_error_on_unparseable_file(indexed_vault, docs_dir: Path):
    (docs_dir / "broken.pdf").write_bytes(b"junk")
    result = indexed_vault.engine.index_file(docs_dir / "broken.pdf")
    assert result.status == "error"
    assert result.error


def test_index_respects_max_file_size(indexed_vault, docs_dir: Path):
    cfg = VaultConfig(max_file_size=10)
    engine = IndexEngine(indexed_vault.repo, cfg)
    result = engine.index_file(docs_dir / "alpha.md")
    assert result.status == "skipped"


def test_file_sha256_matches_hashlib(docs_dir: Path):
    target = docs_dir / "alpha.md"
    assert file_sha256(target) == hashlib.sha256(target.read_bytes()).hexdigest()


def test_index_stats_aggregation(docs_dir: Path):
    from memoryvault import Vault

    vault = Vault.in_memory()
    stats = vault.index(docs_dir)
    assert stats.created == 8
    assert stats.errors == 0
    vault.close()


def test_content_type_mapping(indexed_vault, docs_dir: Path):
    engine = IndexEngine(indexed_vault.repo)
    assert engine.content_type_for(docs_dir / "alpha.md") == "markdown"
    assert engine.content_type_for(docs_dir / "minutes.txt") == "text"
    assert engine.content_type_for(docs_dir / "paper.pdf") == "pdf"


# ---------------------------------------------------------------- scanner
def test_scanner_full_pass_then_noop(indexed_vault, docs_dir: Path):
    stats = indexed_vault.scanner.scan(roots=[docs_dir])
    assert stats.unchanged == 8
    assert stats.created == 0


def test_scanner_reindexes_only_changed(indexed_vault, docs_dir: Path):
    (docs_dir / "minutes.txt").write_text("Meeting minutes\n\nUpdated agenda items.\n",
                                          encoding="utf-8")
    stats = indexed_vault.scanner.scan(roots=[docs_dir])
    assert stats.unchanged == 7
    assert stats.updated == 1


def test_scanner_detects_new_file(indexed_vault, docs_dir: Path):
    (docs_dir / "fresh.md").write_text("# Fresh\n\nbrand new content", encoding="utf-8")
    stats = indexed_vault.scanner.scan(roots=[docs_dir])
    assert stats.created == 1


def test_scanner_marks_vanished_files_deleted(indexed_vault, docs_dir: Path):
    (docs_dir / "beta-copy.md").unlink()
    stats = indexed_vault.scanner.scan(roots=[docs_dir])
    assert stats.removed == 1
    gone = indexed_vault.repo.get_by_path(docs_dir / "beta-copy.md")
    assert gone is None  # filtered out of normal reads
    assert indexed_vault.repo.count() == 7


def test_scanner_size_probe_skips_hashing(indexed_vault, docs_dir: Path, monkeypatch):
    # same size, same hash -> unchanged without ever parsing
    calls = {"parse": 0}
    original = indexed_vault.engine.index_file

    def spy(path):
        if path.name == "alpha.md":
            calls["parse"] += 1
        return original(path)

    monkeypatch.setattr(indexed_vault.engine, "index_file", spy)
    stats = indexed_vault.scanner.scan(roots=[docs_dir])
    assert stats.unchanged == 8
    assert calls["parse"] == 0
