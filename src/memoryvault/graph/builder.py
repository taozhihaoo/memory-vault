"""Build a documents/tags/topics knowledge graph from the database.

Node kinds
----------
* ``document`` — every stored document.
* ``tag``      — explicit tags (frontmatter, manual).
* ``topic``    — auto-extracted keywords (deterministic TF ranking).

Edge kinds
----------
* ``has_tag``   document -> tag
* ``has_topic`` document -> topic
* ``mentions``  document -> document (markdown links / wikilinks resolved
  against file paths and titles)
* ``cooccurs``  tag <-> tag (share at least one document)
* ``similar``   document <-> document (SimHash near-duplicates)
"""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from pathlib import Path, PurePosixPath
from typing import Any

from memoryvault.config import VaultConfig
from memoryvault.database.repository import DocumentRepository


class GraphBuilder:
    """Materialises the knowledge graph as plain ``{"nodes", "edges"}`` dicts."""

    def __init__(self, repo: DocumentRepository, config: VaultConfig | None = None) -> None:
        self.repo = repo
        self.config = config or VaultConfig()

    # ---------------------------------------------------------------- public
    def build(
        self,
        *,
        include_similar: bool = True,
        include_cooccurrence: bool = True,
        limit: int | None = None,
    ) -> dict[str, Any]:
        nodes: dict[str, dict[str, Any]] = {}
        edges: list[dict[str, Any]] = []

        documents = self.repo.list_documents(limit=self.repo.count())
        if limit is not None:
            documents = documents[:limit]

        doc_edges = self._mention_edges(documents)

        for doc in documents:
            nodes[f"doc:{doc.id}"] = {
                "id": f"doc:{doc.id}",
                "kind": "document",
                "label": doc.title or Path(doc.path).name,
                "document_id": doc.id,
                "path": doc.path,
                "content_type": doc.content_type,
                "word_count": doc.word_count,
                "modified_at": doc.modified_at,
            }

        tag_docs: dict[str, list[int]] = defaultdict(list)
        topic_docs: dict[str, list[int]] = defaultdict(list)
        for doc in documents:
            assert doc.id is not None
            for tag in doc.tags:
                tag_docs[tag].append(doc.id)
            for topic in doc.topics:
                topic_docs[topic].append(doc.id)

        for tag, doc_ids in sorted(tag_docs.items()):
            nodes[f"tag:{tag}"] = {
                "id": f"tag:{tag}", "kind": "tag", "label": tag,
                "degree": len(doc_ids),
            }
            for doc_id in doc_ids:
                edges.append(self._edge(f"doc:{doc_id}", f"tag:{tag}", "has_tag"))

        for topic, doc_ids in sorted(topic_docs.items()):
            nodes[f"topic:{topic}"] = {
                "id": f"topic:{topic}", "kind": "topic", "label": topic,
                "degree": len(doc_ids),
            }
            for doc_id in doc_ids:
                edges.append(self._edge(f"doc:{doc_id}", f"topic:{topic}", "has_topic"))

        edges.extend(doc_edges)

        if include_cooccurrence:
            edges.extend(self._cooccurrence_edges(tag_docs, max_tags=self.config.max_cooccurrence_tags))

        if include_similar:
            edges.extend(self._similarity_edges())

        # Degree counts for documents, used for graph layout sizing.
        for edge in edges:
            for endpoint in (edge["source"], edge["target"]):
                if endpoint in nodes and nodes[endpoint]["kind"] == "document":
                    nodes[endpoint]["degree"] = nodes[endpoint].get("degree", 0) + 1

        return {
            "nodes": list(nodes.values()),
            "edges": self._dedupe_edges(edges),
            "meta": {
                "document_count": len(documents),
                "tag_count": len(tag_docs),
                "topic_count": len(topic_docs),
                "edge_count": len(edges),
            },
        }

    def neighborhood(self, document_id: int, *, depth: int = 1) -> dict[str, Any]:
        """Sub-graph of *document_id* and its related documents."""
        graph = self.build()
        keep: set[str] = set()
        frontier = {f"doc:{document_id}"}
        for _ in range(max(depth, 1)):
            next_frontier: set[str] = set()
            for edge in graph["edges"]:
                if edge["source"] in frontier:
                    next_frontier.add(edge["target"])
                if edge["target"] in frontier:
                    next_frontier.add(edge["source"])
            frontier = next_frontier - keep
            keep |= next_frontier
        keep.add(f"doc:{document_id}")
        nodes = [n for n in graph["nodes"] if n["id"] in keep]
        edges = [
            e for e in graph["edges"] if e["source"] in keep and e["target"] in keep
        ]
        return {"nodes": nodes, "edges": edges, "meta": {"focus": document_id}}

    # --------------------------------------------------------------- internal
    def _mention_edges(self, documents) -> list[dict[str, Any]]:  # noqa: ANN001
        """Resolve doc-to-doc markdown links and wikilinks."""
        by_stem: dict[str, int] = {}
        by_title: dict[str, int] = {}
        by_relpath: dict[str, int] = {}
        for doc in documents:
            if doc.id is None:
                continue
            name = PurePosixPath(doc.path).name
            by_stem.setdefault(Path(name).stem.lower(), doc.id)
            if doc.title:
                by_title.setdefault(doc.title.lower(), doc.id)
            by_relpath[name.lower()] = doc.id

        edges: list[dict[str, Any]] = []
        seen: set[tuple[int, int]] = set()
        for doc in documents:
            if doc.id is None:
                continue
            for link in doc.metadata.get("links", []):
                target_id = self._resolve_link(link, by_stem, by_title, by_relpath)
                if target_id is not None and target_id != doc.id:
                    key = (doc.id, target_id)
                    if key not in seen:
                        seen.add(key)
                        edges.append(
                            self._edge(f"doc:{doc.id}", f"doc:{target_id}", "mentions")
                        )
        return edges

    @staticmethod
    def _resolve_link(
        link: str,
        by_stem: dict[str, int],
        by_title: dict[str, int],
        by_relpath: dict[str, int],
    ) -> int | None:
        clean = link.strip().strip("./")
        candidates = [
            PurePosixPath(clean).name.lower(),
            PurePosixPath(clean).stem.lower(),
            clean.lower(),
            clean.removesuffix(".md").lower(),
        ]
        for candidate in candidates:
            if candidate in by_relpath:
                return by_relpath[candidate]
            if candidate in by_stem:
                return by_stem[candidate]
            if candidate in by_title:
                return by_title[candidate]
        return None

    @staticmethod
    def _cooccurrence_edges(
        tag_docs: dict[str, list[int]], *, max_tags: int = 30
    ) -> list[dict[str, Any]]:
        """Pairwise tag co-occurrence, capped to the most-connected tags."""
        tags = sorted(tag_docs, key=lambda t: (-len(tag_docs[t]), t))[:max_tags]
        edges = []
        for i, tag_a in enumerate(tags):
            docs_a = set(tag_docs[tag_a])
            for tag_b in tags[i + 1:]:
                shared = docs_a & set(tag_docs[tag_b])
                if shared:
                    edges.append(
                        {
                            **GraphBuilder._edge(
                                f"tag:{tag_a}", f"tag:{tag_b}", "cooccurs"
                            ),
                            "weight": len(shared),
                        }
                    )
        return edges

    def _similarity_edges(self) -> list[dict[str, Any]]:
        from memoryvault.dedup import DuplicateDetector

        detector = DuplicateDetector(
            self.repo, threshold=self.config.simhash_threshold
        )
        edges = []
        for group in detector.find_similar_pairs():
            a, b = group.document_ids
            edges.append(
                {
                    **self._edge(f"doc:{a}", f"doc:{b}", "similar"),
                    "weight": round(group.similarity or 0, 4),
                }
            )
        return edges

    @staticmethod
    def _edge(source: str, target: str, kind: str) -> dict[str, Any]:
        return {"source": source, "target": target, "kind": kind}

    @staticmethod
    def _dedupe_edges(edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen: dict[tuple[str, str, str], dict[str, Any]] = {}
        for edge in edges:
            key = (edge["source"], edge["target"], edge["kind"])
            if key not in seen:
                seen[key] = edge
            elif "weight" in edge:
                seen[key]["weight"] = max(seen[key].get("weight", 0), edge["weight"])
        return list(seen.values())
