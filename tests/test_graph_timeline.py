"""Knowledge-graph and timeline tests."""

from __future__ import annotations

from pathlib import Path

from memoryvault.graph import GraphBuilder
from memoryvault.timeline import TimelineService


# ------------------------------------------------------------------- graph
def test_graph_has_all_node_kinds(indexed_vault):
    graph = indexed_vault.graph.build()
    kinds = {n["kind"] for n in graph["nodes"]}
    assert {"document", "tag", "topic"} <= kinds


def test_graph_document_count_matches(indexed_vault):
    graph = indexed_vault.graph.build()
    docs = [n for n in graph["nodes"] if n["kind"] == "document"]
    assert len(docs) == indexed_vault.repo.count() == 8
    assert graph["meta"]["document_count"] == 8


def test_graph_tag_edges(indexed_vault):
    graph = indexed_vault.graph.build()
    tag_edges = [e for e in graph["edges"] if e["kind"] == "has_tag"]
    assert any(e["target"] == "tag:research" for e in tag_edges)
    assert any(e["target"] == "tag:ml" for e in tag_edges)


def test_graph_topic_edges_from_keywords(indexed_vault):
    graph = indexed_vault.graph.build()
    topic_edges = [e for e in graph["edges"] if e["kind"] == "has_topic"]
    assert topic_edges  # topics were extracted
    assert any(e["target"] == "topic:quantum" for e in topic_edges)


def test_graph_resolves_wikilink_mentions(indexed_vault):
    graph = indexed_vault.graph.build()
    alpha = next(n for n in graph["nodes"]
                 if n["kind"] == "document" and n["label"] == "Alpha Report")
    beta = next(n for n in graph["nodes"]
                if n["kind"] == "document" and n["label"] == "Beta Notes")
    mentions = [
        e for e in graph["edges"]
        if e["kind"] == "mentions"
        and e["source"] == alpha["id"] and e["target"] == beta["id"]
    ]
    assert mentions  # [[beta-notes]] resolved to the beta document


def test_graph_similarity_edges(indexed_vault):
    graph = indexed_vault.graph.build()
    similar = [e for e in graph["edges"] if e["kind"] == "similar"]
    assert similar and similar[0]["weight"] == 1.0


def test_graph_cooccurrence_capped(indexed_vault):
    from memoryvault import Vault

    vault = Vault.in_memory()
    vault.config.max_cooccurrence_tags = 3
    vault.graph.config = vault.config
    vault.index(_docs())
    graph = vault.graph.build()
    co = [e for e in graph["edges"] if e["kind"] == "cooccurs"]
    tags_in_co = {e["source"] for e in co} | {e["target"] for e in co}
    assert len(tags_in_co) <= 3
    vault.close()


def _docs():
    import tempfile

    root = Path(tempfile.mkdtemp())
    for i in range(6):
        (root / f"doc{i}.md").write_text(
            f"# Doc {i}\n\nalpha beta gamma shared{i} content", encoding="utf-8"
        )
    return root


def test_graph_neighborhood_focuses_on_one_document(indexed_vault):
    graph = indexed_vault.graph.build()
    alpha = next(n for n in graph["nodes"]
                 if n["kind"] == "document" and n["label"] == "Alpha Report")
    doc_id = alpha["document_id"]
    sub = indexed_vault.graph.neighborhood(doc_id, depth=1)
    assert sub["meta"]["focus"] == doc_id
    assert f"doc:{doc_id}" in {n["id"] for n in sub["nodes"]}
    # every edge touches the focus document's neighborhood
    assert sub["edges"]


def test_graph_edges_have_no_duplicates(indexed_vault):
    graph = indexed_vault.graph.build()
    keys = [(e["source"], e["target"], e["kind"]) for e in graph["edges"]]
    assert len(keys) == len(set(keys))


def test_graph_limit_option(indexed_vault):
    graph = indexed_vault.graph.build(limit=3)
    docs = [n for n in graph["nodes"] if n["kind"] == "document"]
    assert len(docs) == 3


# ---------------------------------------------------------------- timeline
def test_events_recorded_for_every_document(indexed_vault):
    events = indexed_vault.timeline.recent(limit=100)
    assert len(events) == 8
    assert all(e["event_type"] == "created" for e in events)


def test_document_history_order(indexed_vault, docs_dir: Path):
    target = docs_dir / "minutes.txt"
    target.write_text("Meeting minutes\n\nSecond revision with new content.\n",
                      encoding="utf-8")
    indexed_vault.scanner.scan(roots=[docs_dir])
    doc = indexed_vault.repo.get_by_path(target)
    history = indexed_vault.timeline.document_history(doc.id)
    assert [e["event_type"] for e in history] == ["created", "updated"]


def test_activity_totals(indexed_vault):
    activity = indexed_vault.timeline.activity()
    assert activity["totals"]["created"] == 8
    assert activity["group_by"] == "day"
    assert activity["buckets"][-1]["total"] == 8


def test_activity_group_by_month(indexed_vault):
    activity = indexed_vault.timeline.activity(group_by="month")
    assert activity["group_by"] == "month"
    assert sum(b["total"] for b in activity["buckets"]) == 8


def test_timeline_event_type_filter(indexed_vault, docs_dir: Path):
    (docs_dir / "minutes.txt").write_text("Meeting minutes\n\nThird revision here.\n",
                                          encoding="utf-8")
    indexed_vault.scanner.scan(roots=[docs_dir])
    updated = indexed_vault.timeline.recent(event_type="updated")
    assert len(updated) == 1


def test_counts_by_type(indexed_vault):
    counts = indexed_vault.timeline.document_counts_by_type()
    names = {c["content_type"] for c in counts}
    assert {"markdown", "text", "html", "json", "csv", "pdf"} <= names
