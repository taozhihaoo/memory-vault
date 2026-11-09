"""Regression tests for the 1.0.1 correctness and security fixes.

Every test here reproduces a concrete defect found in the 1.0.0 release:
data loss during incremental scans, stored XSS through search highlights,
FTS5 500 errors, wrong counts, a tag/topic primary-key collision and an
over-permissive local API.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from memoryvault import Vault
from memoryvault.api import create_app
from memoryvault.config import VaultConfig
from memoryvault.database.connection import connect
from memoryvault.database.repository import Document, DocumentRepository


@pytest.fixture()
def repo() -> DocumentRepository:
    conn = connect(":memory:")
    yield DocumentRepository(conn)
    conn.close()


# ----------------------------------------------------- 1. scanner path boundary
def test_scanning_one_root_does_not_delete_sibling_prefix(vault, tmp_path):
    """``/docs`` must not swallow ``/docs-archive`` (plain startswith did)."""
    docs = tmp_path / "docs"
    archive = tmp_path / "docs-archive"
    docs.mkdir()
    archive.mkdir()
    (docs / "a.md").write_text("# A\n\nalpha content", encoding="utf-8")
    (archive / "b.md").write_text("# B\n\nbeta content", encoding="utf-8")
    vault.index(docs)
    vault.index(archive)

    stats = vault.scanner.scan(roots=[docs])

    assert stats.removed == 0
    assert vault.repo.count() == 2
    assert vault.repo.get_by_path(archive / "b.md") is not None


def test_index_directory_does_not_delete_sibling_prefix(vault, tmp_path):
    docs = tmp_path / "notes"
    archive = tmp_path / "notes-old"
    docs.mkdir()
    archive.mkdir()
    (docs / "a.md").write_text("# A\n\nalpha", encoding="utf-8")
    (archive / "b.md").write_text("# B\n\nbeta", encoding="utf-8")
    vault.index(archive)
    vault.index(docs)
    assert vault.repo.get_by_path(archive / "b.md") is not None


# ------------------------------------------------------------ 2. XSS in search
def test_search_highlight_escapes_document_html(vault, tmp_path):
    root = tmp_path / "evil"
    root.mkdir()
    (root / "evil.md").write_text(
        '# <img src=x onerror="alert(1)">\n\n'
        "secret <script>alert(2)</script> payload",
        encoding="utf-8",
    )
    vault.index(root)
    hit = vault.search.search("secret")["results"][0]

    assert "<mark>secret</mark>" in hit.snippet
    assert "<script>" not in hit.snippet
    assert "<img" not in hit.snippet
    assert "&lt;script&gt;" in hit.snippet
    assert "<img" not in hit.title_highlighted
    assert "&lt;img" in hit.title_highlighted


def test_custom_markers_are_still_applied_and_text_is_escaped(vault, tmp_path):
    root = tmp_path / "evil"
    root.mkdir()
    (root / "x.md").write_text("# Title\n\n<svg onload=1> word", encoding="utf-8")
    vault.index(root)
    hit = vault.search.search("word", highlight_pre="[", highlight_post="]")["results"][0]
    assert "[word]" in hit.snippet.lower()
    assert "<svg" not in hit.snippet


# ----------------------------------------------------- 3. FTS5 query robustness
def test_exclusion_only_query_does_not_raise(indexed_vault):
    found = indexed_vault.search.search("-zzzznotpresent")
    assert found["total"] == indexed_vault.repo.count()
    assert found["results"]


def test_multiple_exclusions_do_not_raise(indexed_vault):
    found = indexed_vault.search.search("-quantum -zzzznotpresent")
    assert 0 <= found["total"] <= indexed_vault.repo.count()


def test_dangling_or_does_not_become_a_literal_term():
    from memoryvault.search.engine import build_match_query

    assert build_match_query("quantum OR") == '"quantum"*'
    assert build_match_query("OR quantum") == '"quantum"*'


def test_api_search_never_500s_on_exclusion_query(indexed_vault):
    from fastapi.testclient import TestClient

    with TestClient(create_app(vault=indexed_vault)) as http:
        assert http.get("/api/search", params={"q": "-quantum"}).status_code == 200
        assert http.get("/api/search", params={"q": "-a -b"}).status_code == 200


# ------------------------------------------------------- 4. format registry
def test_cjk_keywords_are_real_words_not_arbitrary_chunks():
    from memoryvault.keywords import extract_keywords

    topics = extract_keywords(
        "量子计算导论。量子计算机使用量子比特存储信息。"
        "温室里的番茄长势良好，温室湿度保持在目标范围内。"
    )
    assert "量子" in topics
    assert "温室" in topics
    assert not any("不" in t or "与" in t for t in topics)
    for topic in topics:
        assert not topic.startswith(("子", "户", "艺")), f"garbled topic: {topic}"


def test_cjk_word_count_counts_characters():
    from memoryvault.textutil import count_words

    assert count_words("量子计算") == 4
    assert count_words("Hello 量子") == 3
    assert count_words("Hello, world! Hello again.") == 4


def test_all_registered_formats_are_indexable_by_default():
    from memoryvault.parser import supported_extensions

    cfg = VaultConfig()
    assert set(supported_extensions()) <= set(cfg.extensions)
    assert {"log", "tsv", "text"} <= set(cfg.extensions)


def test_log_and_tsv_files_are_indexed(vault, tmp_path):
    root = tmp_path / "mixed"
    root.mkdir()
    (root / "run.log").write_text("service started ok", encoding="utf-8")
    (root / "data.tsv").write_text("name\tqty\nbolt\t12\n", encoding="utf-8")
    stats = vault.index(root)
    assert stats.created == 2


# ------------------------------------------------- 5. tag/topic schema (v2)
def test_tag_and_topic_can_share_one_name(vault, tmp_path):
    root = tmp_path / "collide"
    root.mkdir()
    (root / "x.md").write_text(
        "---\ntags: [research]\n---\n# Research\n\n"
        "research research research knowledge research",
        encoding="utf-8",
    )
    vault.index(root)
    doc = vault.repo.list_documents(limit=1)[0]
    assert "research" in doc.tags
    assert "research" in doc.topics


def test_list_tags_counts_distinct_documents(repo: DocumentRepository):
    doc, _ = repo.upsert(Document(path="/tmp/t.md", sha256="a" * 64))
    repo.set_tags(doc.id, ["shared"], source="tag")
    repo.set_tags(doc.id, ["shared"], source="topic")
    assert repo.list_tags()[0]["document_count"] == 1


def test_v1_vault_is_migrated_to_v2(tmp_path):
    """Existing 1.0.0 databases must keep their data and gain the new key."""
    db = tmp_path / "legacy.db"
    conn = sqlite3.connect(db)
    conn.executescript(
        """
        CREATE TABLE schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        INSERT INTO schema_meta VALUES ('schema_version', '1');
        CREATE TABLE documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT, path TEXT NOT NULL UNIQUE,
            title TEXT NOT NULL DEFAULT '', content TEXT NOT NULL DEFAULT '',
            content_type TEXT NOT NULL DEFAULT '', file_size INTEGER NOT NULL DEFAULT 0,
            sha256 TEXT NOT NULL, simhash TEXT, metadata TEXT NOT NULL DEFAULT '{}',
            word_count INTEGER NOT NULL DEFAULT 0, created_at TEXT, modified_at TEXT,
            indexed_at TEXT NOT NULL, deleted INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE tags (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE);
        CREATE TABLE document_tags (
            document_id INTEGER NOT NULL, tag_id INTEGER NOT NULL,
            source TEXT NOT NULL DEFAULT 'auto',
            PRIMARY KEY (document_id, tag_id)
        );
        INSERT INTO documents (id, path, title, sha256, indexed_at)
            VALUES (1, '/tmp/legacy.md', 'Legacy', 'aaaa', '2026-01-01T00:00:00Z');
        INSERT INTO tags (id, name) VALUES (1, 'legacy');
        INSERT INTO document_tags VALUES (1, 1, 'tag');
        """
    )
    conn.commit()
    conn.close()

    upgraded = connect(db)
    assert upgraded.execute(
        "SELECT value FROM schema_meta WHERE key='schema_version'"
    ).fetchone()["value"] == "2"
    assert upgraded.execute(
        "SELECT COUNT(*) AS n FROM document_tags"
    ).fetchone()["n"] == 1
    repo = DocumentRepository(upgraded)
    repo.set_tags(1, ["legacy"], source="topic")
    assert repo.tags_for(1, source="tag") == ["legacy"]
    assert repo.topics_for(1) == ["legacy"]
    upgraded.close()


# ------------------------------------------------------------ 6. counts/histogram
def test_count_events_counts_events_not_documents(repo: DocumentRepository):
    doc, _ = repo.upsert(Document(path="/tmp/a.md", sha256="a" * 64))
    repo.add_event(document_id=doc.id, path="/tmp/a.md", event_type="indexed")
    assert repo.count() == 1
    assert repo.count_events() == 2
    assert repo.count_events(event_type="created") == 1


def test_activity_histogram_uses_calendar_days(repo: DocumentRepository):
    doc, _ = repo.upsert(Document(path="/tmp/a.md", sha256="a" * 64))
    repo.add_event(
        document_id=doc.id, path="/tmp/a.md", event_type="indexed",
        occurred_at="2001-01-01T00:00:00Z",
    )
    recent = repo.activity_histogram(days=7)
    all_time = repo.activity_histogram(days=36500)
    assert all(bucket["date"] != "2001-01-01" for bucket in recent)
    assert any(bucket["date"] == "2001-01-01" for bucket in all_time)


def test_parallel_reads_never_clobber_each_others_cursors(indexed_vault):
    """FastAPI runs sync endpoints in a thread pool sharing one connection."""
    from concurrent.futures import ThreadPoolExecutor

    def probe(_):
        row = indexed_vault.repo.conn.execute(
            "SELECT COUNT(*) AS n FROM documents WHERE deleted = 0"
        ).fetchone()
        assert row is not None, "a concurrent statement consumed this result"
        return row["n"]

    with ThreadPoolExecutor(max_workers=12) as pool:
        results = list(pool.map(probe, range(240)))
    assert results == [8] * 240


def test_api_health_is_stable_under_parallel_requests(indexed_vault):
    from concurrent.futures import ThreadPoolExecutor

    from fastapi.testclient import TestClient

    with TestClient(create_app(vault=indexed_vault)) as http:
        with ThreadPoolExecutor(max_workers=8) as pool:
            statuses = list(pool.map(lambda _: http.get("/api/health").status_code, range(32)))
    assert statuses == [200] * 32


def test_api_timeline_events_total_is_event_count(indexed_vault):
    from fastapi.testclient import TestClient

    with TestClient(create_app(vault=indexed_vault)) as http:
        body = http.get("/api/timeline/events", params={"limit": 3}).json()
    assert body["total"] == indexed_vault.repo.count_events()
    assert len(body["events"]) == 3


# --------------------------------------------------------------- 7. HTTP surface
def test_api_does_not_allow_arbitrary_origins(indexed_vault):
    from fastapi.testclient import TestClient

    with TestClient(create_app(vault=indexed_vault)) as http:
        evil = http.get("/api/health", headers={"Origin": "https://evil.example"})
        local = http.get("/api/health", headers={"Origin": "http://localhost:5173"})
    assert "access-control-allow-origin" not in evil.headers
    assert local.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_unknown_api_route_is_json_404_when_dashboard_is_mounted(indexed_vault):
    from fastapi.testclient import TestClient

    dist = Path(__file__).resolve().parents[1] / "frontend" / "dist"
    if not (dist / "index.html").is_file():
        pytest.skip("frontend bundle not built")
    indexed_vault.config.frontend_dist = dist
    app = create_app(vault=indexed_vault)
    with TestClient(app) as http:
        response = http.get("/api/definitely-missing")
        assert response.status_code == 404
        assert response.headers["content-type"].startswith("application/json")


def test_spa_fallback_rejects_path_traversal(indexed_vault, tmp_path):
    from fastapi.testclient import TestClient

    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html>dashboard</html>", encoding="utf-8")
    secret = tmp_path / "secret.txt"
    secret.write_text("SENSITIVE", encoding="utf-8")
    indexed_vault.config.frontend_dist = dist
    app = create_app(vault=indexed_vault)
    with TestClient(app) as http:
        body = http.get("/%2e%2e%2fsecret.txt").text
    assert "SENSITIVE" not in body


# --------------------------------------------------------------- 8. graph edges
def test_graph_limit_has_no_dangling_edges(indexed_vault):
    graph = indexed_vault.graph.build(limit=1)
    node_ids = {node["id"] for node in graph["nodes"]}
    assert all(
        edge["source"] in node_ids and edge["target"] in node_ids
        for edge in graph["edges"]
    )
    assert graph["meta"]["edge_count"] == len(graph["edges"])


# ------------------------------------------------------------ 9. re-scan roots
def test_rescan_without_roots_uses_remembered_directory(vault, tmp_path):
    root = tmp_path / "notes"
    root.mkdir()
    (root / "a.md").write_text("# A\n\nalpha", encoding="utf-8")
    vault.index(root)
    (root / "b.md").write_text("# B\n\nbeta", encoding="utf-8")

    stats = vault.scanner.scan()  # no roots, no configured watch paths

    assert stats.created == 1
    assert vault.repo.count() == 2


def test_api_scan_without_roots_refreshes_vault(vault, tmp_path):
    from fastapi.testclient import TestClient

    root = tmp_path / "notes"
    root.mkdir()
    (root / "a.md").write_text("# A\n\nalpha", encoding="utf-8")
    vault.index(root)
    (root / "b.md").write_text("# B\n\nbeta", encoding="utf-8")
    with TestClient(create_app(vault=vault)) as http:
        body = http.post("/api/scan").json()
    assert body["created"] == 1


def test_remembered_roots_survive_reopen(tmp_path):
    root = tmp_path / "notes"
    root.mkdir()
    (root / "a.md").write_text("# A\n\nalpha", encoding="utf-8")
    db = tmp_path / "vault.db"
    with Vault.open(db) as vault:
        vault.index(root)
    with Vault.open(db) as vault:
        assert vault.scanner.remembered_roots()
        assert json.loads(vault.repo.get_setting("watch_roots"))
