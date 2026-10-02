"""FastAPI endpoint tests (httpx TestClient against the real app)."""

from __future__ import annotations

import pytest

from memoryvault.api import create_app


@pytest.fixture()
def client(indexed_vault):
    from fastapi.testclient import TestClient

    app = create_app(vault=indexed_vault)
    with TestClient(app) as http:
        yield http


def test_health(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["documents"] == 8


def test_stats(client):
    body = client.get("/api/stats").json()
    assert body["documents"] == 8
    assert body["words"] > 0
    assert "markdown" in body["content_types"]


def test_list_documents(client):
    body = client.get("/api/documents", params={"limit": 3}).json()
    assert body["total"] == 8
    assert len(body["documents"]) == 3


def test_list_documents_filter_type(client):
    body = client.get("/api/documents", params={"content_type": "markdown"}).json()
    assert body["total"] == 3


def test_get_document_missing_404(client):
    assert client.get("/api/documents/99999").status_code == 404


def test_get_document_detail(client):
    listing = client.get("/api/documents", params={"limit": 1}).json()
    doc_id = listing["documents"][0]["id"]
    body = client.get(f"/api/documents/{doc_id}").json()
    assert body["id"] == doc_id
    assert body["sha256"]
    assert "content" not in body  # detail excludes the full body


def test_document_content_endpoint(client):
    listing = client.get("/api/documents", params={"content_type": "json"}).json()
    doc_id = listing["documents"][0]["id"]
    body = client.get(f"/api/documents/{doc_id}/content").json()
    assert "greenhouse" in body["content"]
    truncated = client.get(
        f"/api/documents/{doc_id}/content", params={"max_chars": 5}
    ).json()
    assert len(truncated["content"]) == 5


def test_search_endpoint(client):
    body = client.get("/api/search", params={"q": "machine learning"}).json()
    assert body["total"] >= 2
    hit = body["results"][0]
    assert hit["score"] > 0
    assert "<mark>" in hit["snippet"]
    assert body["took_ms"] is not None


def test_search_requires_query(client):
    assert client.get("/api/search").status_code == 422


def test_search_filter_tag(client):
    body = client.get("/api/search", params={"q": "greenhouse", "tag": "iot"}).json()
    assert body["total"] == 1


def test_suggest_endpoint(client):
    body = client.get("/api/suggest", params={"q": "quan"}).json()
    assert any(s["term"].startswith("quan") for s in body["suggestions"])


def test_graph_endpoint(client):
    body = client.get("/api/graph").json()
    kinds = {n["kind"] for n in body["nodes"]}
    assert {"document", "tag", "topic"} <= kinds
    assert body["meta"]["document_count"] == 8


def test_graph_neighborhood(client):
    listing = client.get("/api/documents", params={"limit": 50}).json()
    alpha = next(d for d in listing["documents"] if d["title"] == "Alpha Report")
    body = client.get(f"/api/graph/neighborhood/{alpha['id']}").json()
    assert body["meta"]["focus"] == alpha["id"]
    assert client.get("/api/graph/neighborhood/99999").status_code == 404


def test_timeline_endpoint(client):
    body = client.get("/api/timeline").json()
    assert body["totals"]["created"] == 8
    assert body["buckets"]


def test_timeline_events(client):
    body = client.get("/api/timeline/events").json()
    assert len(body["events"]) == 8


def test_document_history_endpoint(client):
    listing = client.get("/api/documents", params={"limit": 50}).json()
    alpha = next(d for d in listing["documents"] if d["title"] == "Alpha Report")
    body = client.get(f"/api/documents/{alpha['id']}/history").json()
    assert body["events"][0]["event_type"] == "created"
    assert client.get("/api/documents/99999/history").status_code == 404


def test_related_endpoint(client):
    listing = client.get("/api/documents", params={"limit": 50}).json()
    alpha = next(d for d in listing["documents"] if d["title"] == "Alpha Report")
    body = client.get(f"/api/documents/{alpha['id']}/related").json()
    assert body["query"].startswith("related:")
    assert all(h["document_id"] != alpha["id"] for h in body["results"])


def test_similar_endpoint(client):
    body = client.get("/api/duplicates").json()
    assert body["exact"] or body["similar"]
    group = (body["exact"] or body["similar"])[0]
    target = group["document_ids"][0]
    sim = client.get(f"/api/documents/{target}/similar").json()
    assert "similar" in sim


def test_duplicates_endpoint(client):
    body = client.get("/api/duplicates").json()
    exact_ids = [g["document_ids"] for g in body["exact"]]
    assert [2, 3] in [sorted(ids) for ids in exact_ids]


def test_tags_endpoint(client):
    body = client.get("/api/tags").json()
    names = {t["name"] for t in body}
    assert {"research", "ml", "iot"} <= names


def test_scan_endpoint_without_roots(indexed_vault, docs_dir):
    from fastapi.testclient import TestClient

    indexed_vault.config.watch_paths = [docs_dir]
    app = create_app(vault=indexed_vault)
    with TestClient(app) as http:
        body = http.post("/api/scan").json()
        assert body["unchanged"] == 8


def test_scan_endpoint_with_roots(client, docs_dir):
    body = client.post("/api/scan", json=[str(docs_dir)]).json()
    assert body["unchanged"] == 8


def test_app_without_vault_uses_config(tmp_path, docs_dir):
    from fastapi.testclient import TestClient

    from memoryvault.config import VaultConfig

    cfg = VaultConfig(db_path=tmp_path / "api-vault.db", watch_paths=[docs_dir])
    app = create_app(config=cfg)
    with TestClient(app) as http:
        assert http.get("/api/health").json()["documents"] == 0
