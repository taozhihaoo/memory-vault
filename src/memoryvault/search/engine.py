"""Search engine on top of SQLite FTS5.

* Safe user-query to MATCH-expression translation.
* BM25 ranking (FTS5's built-in ``bm25()``).
* Snippet and term highlighting via ``snippet()`` / ``highlight()``.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, field
from typing import Any

from memoryvault.database.repository import DocumentRepository

_TOKEN_RE = re.compile(r'"[^"]*"|[^\s"]+')


@dataclass(slots=True)
class SearchResult:
    """One ranked hit."""

    document_id: int
    path: str
    title: str
    snippet: str
    title_highlighted: str
    score: float
    content_type: str = ""
    modified_at: str | None = None
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "document_id": self.document_id,
            "path": self.path,
            "title": self.title,
            "snippet": self.snippet,
            "title_highlighted": self.title_highlighted,
            "score": round(self.score, 4),
            "content_type": self.content_type,
            "modified_at": self.modified_at,
            "tags": self.tags,
        }


def build_match_query(user_query: str) -> str | None:
    """Translate a raw user query into a safe FTS5 MATCH expression.

    Grammar (kept deliberately small and deterministic):

    * bare words become prefix queries: ``hello`` -> ``"hello"*``
    * quoted strings become exact phrases: ``"exact phrase"``
    * ``-word`` excludes: ``-spam`` -> ``NOT "spam"*``
    * uppercase ``OR`` between terms keeps alternatives

    Returns ``None`` when nothing searchable remains (empty/stopword query).
    """
    tokens = _TOKEN_RE.findall(user_query.strip())
    if not tokens:
        return None

    parts: list[str] = []
    i = 0
    while i < len(tokens):
        token = tokens[i]
        upper = token.upper()
        if upper == "OR" and parts and i + 1 < len(tokens):
            parts.append("OR")
            i += 1
            continue
        if token.startswith("-") and len(token) > 1:
            term = _term_to_match(token[1:], prefix=True)
            if term:
                parts.append(f"NOT {term}")
            i += 1
            continue
        term = _term_to_match(token, prefix=True)
        if term:
            if parts and parts[-1] != "OR":
                parts.append("AND")
            parts.append(term)
        i += 1

    expression = " ".join(parts)
    expression = re.sub(r"^(AND|OR)\s+|\s+(AND|OR)$", "", expression)
    return expression if expression.strip() else None


def _term_to_match(token: str, *, prefix: bool) -> str | None:
    if token.startswith('"') and token.endswith('"') and len(token) >= 2:
        inner = token[1:-1].replace('"', '""')
        return f'"{inner}"' if inner else None
    cleaned = token.strip("*").strip("-")
    if not cleaned or not cleaned.strip("_"):
        return None
    cleaned = cleaned.replace('"', '""')
    return f'"{cleaned}"*' if prefix else f'"{cleaned}"'


class SearchEngine:
    """Runs FTS5 queries against the vault and shapes the results."""

    def __init__(self, repo: DocumentRepository) -> None:
        self.repo = repo

    def search(
        self,
        query: str,
        *,
        limit: int = 20,
        offset: int = 0,
        content_type: str | None = None,
        tag: str | None = None,
        highlight_pre: str = "<mark>",
        highlight_post: str = "</mark>",
    ) -> dict[str, Any]:
        """Return ranked search results with snippets and total count."""
        match_expr = build_match_query(query)
        if not match_expr:
            return {"query": query, "total": 0, "results": []}

        clauses = ["documents_fts MATCH :match"]
        params: dict[str, Any] = {"match": match_expr}
        if content_type:
            clauses.append("d.content_type = :ctype")
            params["ctype"] = content_type
        if tag:
            clauses.append(
                "d.id IN (SELECT dt.document_id FROM document_tags dt"
                " JOIN tags t ON t.id = dt.tag_id WHERE t.name = :tag)"
            )
            params["tag"] = tag
        where = " AND ".join(clauses)

        base_sql = f"""
            FROM documents_fts f
            JOIN documents d ON d.id = f.rowid
            WHERE {where} AND d.deleted = 0
        """

        count_row = self.repo.conn.execute(
            f"SELECT COUNT(*) AS n {base_sql}", params
        ).fetchone()
        total = int(count_row["n"])

        sql = f"""
            SELECT d.id, d.path, d.title, d.content_type, d.modified_at,
                   bm25(documents_fts) AS rank,
                   snippet(documents_fts, 1, :pre, :post, '…', 18) AS snip,
                   highlight(documents_fts, 0, :pre, :post) AS htitle
            {base_sql}
            ORDER BY rank, d.modified_at DESC
            LIMIT :limit OFFSET :offset
        """
        rows = self.repo.conn.execute(
            sql, {**params, "pre": highlight_pre, "post": highlight_post,
                  "limit": limit, "offset": offset}
        ).fetchall()

        results: list[SearchResult] = []
        for row in rows:
            # FTS5 ranks by descending relevance with *negative* bm25 values;
            # negate so a bigger score is a better match for consumers.
            results.append(
                SearchResult(
                    document_id=row["id"],
                    path=row["path"],
                    title=row["title"],
                    snippet=row["snip"],
                    title_highlighted=row["htitle"],
                    score=-row["rank"],
                    content_type=row["content_type"],
                    modified_at=row["modified_at"],
                    tags=self.repo.tags_for(row["id"], source="tag"),
                )
            )
        return {"query": query, "total": total, "results": results}

    def suggest(self, prefix: str, *, limit: int = 10) -> list[dict[str, Any]]:
        """Vocabulary terms starting with *prefix*, most frequent first."""
        prefix = prefix.strip().lower()
        if not prefix or not re.fullmatch(r"[\w'-]+", prefix):
            return []
        try:
            self.repo.conn.execute(
                "CREATE VIRTUAL TABLE IF NOT EXISTS search_vocab"
                " USING fts5vocab('documents_fts', 'row')"
            )
            rows = self.repo.conn.execute(
                "SELECT term, doc AS documents FROM search_vocab"
                " WHERE term LIKE ? ORDER BY documents DESC, term LIMIT ?",
                (prefix + "%", limit),
            ).fetchall()
        except sqlite3.DatabaseError:
            return []
        return [{"term": r["term"], "documents": r["documents"]} for r in rows]

    def more_like(self, document_id: int, *, limit: int = 5) -> list[SearchResult]:
        """Simple related-document finder: query FTS with the document's topics."""
        doc = self.repo.get(document_id)
        if doc is None:
            return []
        seeds = (doc.topics or doc.tags or [])[:5]
        if not seeds:
            # fall back to the most distinctive words of the title
            seeds = [w for w in re.findall(r"\w{3,}", doc.title.lower())][:5]
        if not seeds:
            return []
        query = " OR ".join(seeds)
        found = self.search(query, limit=limit + 1)
        return [r for r in found["results"] if r.document_id != document_id][:limit]
