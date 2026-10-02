"""Database layer tests: schema, repository CRUD, tags, events, settings."""

from __future__ import annotations

import json

import pytest

from memoryvault.database.connection import connect
from memoryvault.database.repository import Document, DocumentRepository


@pytest.fixture()
def repo() -> DocumentRepository:
    conn = connect(":memory:")
    yield DocumentRepository(conn)
    conn.close()


def _doc(path: str = "/tmp/a.md", content: str = "hello world", **kw) -> Document:
    return Document(path=path, title="A", content=content, content_type="markdown",
                    sha256=kw.pop("sha256", "0" * 64), **kw)


# ------------------------------------------------------------------ schema
def test_connect_creates_schema(tmp_path):
    conn = connect(tmp_path / "vault.db")
    tables = {
        r["name"]
        for r in conn.execute("SELECT name FROM sqlite_master WHERE type IN ('table','view')")
    }
    assert {"documents", "documents_fts", "tags", "document_tags",
            "document_events", "simhash_bands", "settings", "schema_meta"} <= tables
    conn.close()


def test_schema_version_recorded(tmp_path):
    conn = connect(tmp_path / "vault.db")
    row = conn.execute("SELECT value FROM schema_meta WHERE key='schema_version'").fetchone()
    assert int(row["value"]) >= 1
    conn.close()


def test_fts5_table_functional(repo: DocumentRepository):
    repo.fts_replace(1, "Title", "searchable content words")
    row = repo.conn.execute(
        "SELECT rowid FROM documents_fts WHERE documents_fts MATCH 'searchable'"
    ).fetchone()
    assert row["rowid"] == 1


# ------------------------------------------------------------------- upsert
def test_upsert_creates_then_unchanged(repo: DocumentRepository):
    doc, change = repo.upsert(_doc())
    assert change == "created" and doc.id is not None
    same, change2 = repo.upsert(_doc())
    assert change2 == "unchanged"
    assert same.id == doc.id


def test_upsert_updates_changed_content(repo: DocumentRepository):
    doc, _ = repo.upsert(_doc())
    changed, change = repo.upsert(_doc(sha256="f" * 64, content="new body"))
    assert change == "updated"
    assert changed.id == doc.id
    assert changed.content == "new body"


def test_upsert_reanimates_deleted(repo: DocumentRepository):
    doc, _ = repo.upsert(_doc())
    repo.mark_deleted(doc.id)
    back, change = repo.upsert(_doc(sha256="e" * 64))
    assert change == "updated"
    assert back.deleted is False


def test_upsert_normalizes_path(repo: DocumentRepository, tmp_path):
    target = tmp_path / "x.md"
    target.write_text("hi", encoding="utf-8")
    doc, _ = repo.upsert(_doc(path=str(target)))
    assert doc.path.replace("\\", "/").endswith("x.md")


# -------------------------------------------------------------------- reads
def test_get_returns_none_for_missing(repo: DocumentRepository):
    assert repo.get(999) is None


def test_get_by_path(repo: DocumentRepository):
    doc, _ = repo.upsert(_doc(path="/tmp/unique.md"))
    assert repo.get_by_path("/tmp/unique.md").id == doc.id


def test_list_documents_pagination(repo: DocumentRepository):
    for i in range(5):
        repo.upsert(_doc(path=f"/tmp/{i}.md", sha256=str(i) * 64))
    page = repo.list_documents(limit=2, offset=0)
    assert len(page) == 2
    assert repo.count() == 5


def test_list_documents_filter_content_type(repo: DocumentRepository):
    repo.upsert(_doc(path="/tmp/a.md"))
    repo.upsert(Document(path="/tmp/b.txt", title="B", content="x",
                         content_type="text", sha256="1" * 64))
    only_md = repo.list_documents(content_type="markdown")
    assert len(only_md) == 1 and only_md[0].content_type == "markdown"


def test_document_to_dict_excludes_content(repo: DocumentRepository):
    doc, _ = repo.upsert(_doc(content="secret body"))
    data = doc.to_dict(include_content=False)
    assert "content" not in data
    assert data["title"] == "A"


# --------------------------------------------------------------------- tags
def test_tags_roundtrip(repo: DocumentRepository):
    doc, _ = repo.upsert(_doc())
    repo.set_tags(doc.id, ["alpha", "beta"], source="tag")
    assert repo.tags_for(doc.id) == ["alpha", "beta"]
    tags = repo.list_tags()
    assert {t["name"] for t in tags} == {"alpha", "beta"}


def test_set_tags_replaces_previous(repo: DocumentRepository):
    doc, _ = repo.upsert(_doc())
    repo.set_tags(doc.id, ["one", "two"], source="tag")
    repo.set_tags(doc.id, ["three"], source="tag")
    assert repo.tags_for(doc.id, source="tag") == ["three"]


def test_tag_and_topic_sources_separated(repo: DocumentRepository):
    doc, _ = repo.upsert(_doc())
    repo.set_tags(doc.id, ["manual"], source="tag")
    repo.set_tags(doc.id, ["kw1"], source="topic")
    assert repo.tags_for(doc.id, source="tag") == ["manual"]
    assert repo.topics_for(doc.id) == ["kw1"]


def test_empty_tag_name_rejected(repo: DocumentRepository):
    with pytest.raises(ValueError):
        repo.ensure_tag("   ")


# ------------------------------------------------------------------- events
def test_upsert_logs_created_event(repo: DocumentRepository):
    doc, _ = repo.upsert(_doc())
    events = repo.list_events(document_id=doc.id)
    assert len(events) == 1
    assert events[0].event_type == "created"


def test_mark_deleted_logs_event(repo: DocumentRepository):
    doc, _ = repo.upsert(_doc())
    repo.mark_deleted(doc.id)
    types = [e.event_type for e in repo.list_events(document_id=doc.id)]
    assert sorted(types) == ["created", "deleted"]
    assert repo.get(doc.id) is None
    assert repo.get(doc.id, include_deleted=True) is not None


def test_purge_deleted(repo: DocumentRepository):
    doc, _ = repo.upsert(_doc())
    repo.mark_deleted(doc.id)
    assert repo.purge_deleted() == 1
    assert repo.count(include_deleted=True) == 0


def test_activity_histogram_buckets_by_day(repo: DocumentRepository):
    doc, _ = repo.upsert(_doc())
    histogram = repo.activity_histogram()
    assert histogram and histogram[-1]["total"] >= 1


# ----------------------------------------------------------------- settings
def test_settings_roundtrip(repo: DocumentRepository):
    repo.set_setting("key1", "value1")
    repo.set_setting("key1", "value2")
    assert repo.get_setting("key1") == "value2"
    assert repo.get_setting("missing") is None


# -------------------------------------------------------------------- stats
def test_stats_counts_documents_and_words(repo: DocumentRepository):
    repo.upsert(_doc(content="one two three four"))
    repo.upsert(_doc(path="/tmp/b.md", sha256="b" * 64, content="five six"))
    stats = repo.stats()
    assert stats["documents"] == 2
    assert stats["words"] == 6
    assert stats["content_types"].get("markdown") == 2


# -------------------------------------------------------------------- bands
def test_store_and_query_bands(repo: DocumentRepository):
    doc, _ = repo.upsert(_doc())
    fp = 0b1111000011110000111100001111000011110000111100001111000011110000
    repo.store_bands(doc.id, fp, bands=4)
    candidates = repo.band_candidates(fp, exclude={doc.id})
    assert candidates == set()
    other, _ = repo.upsert(_doc(path="/tmp/other.md", sha256="c" * 64))
    repo.store_bands(other.id, fp ^ 1, bands=4)  # last band identical
    candidates = repo.band_candidates(fp, exclude={doc.id})
    assert other.id in candidates
