"""Search engine on top of SQLite FTS5.

* Safe user-query to MATCH-expression translation.
* BM25 ranking (FTS5's built-in ``bm25()``).
* Snippet and term highlighting via ``snippet()`` / ``highlight()``.

Highlighting is HTML-safe: FTS5 inserts private sentinel characters around
matches, the document text is then HTML-escaped, and only afterwards are the
sentinels replaced with the requested (trusted) marker strings.  This closes
a stored-XSS hole where document content such as ``<img onerror=...>`` used
to be handed to ``dangerouslySetInnerHTML`` verbatim.
"""

from __future__ import annotations

import html
import re
import sqlite3
from dataclasses import dataclass, field
from typing import Any

from memoryvault.database.repository import DocumentRepository

_TOKEN_RE = re.compile(r'"[^"]*"|[^\s"]+')

# Private, single-character markers. FTS5 never sees HTML and the raw
# document text can never inject a tag: everything is escaped first.
_HL_OPEN = "\x01"
_HL_CLOSE = "\x02"


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
    for i, token in enumerate(tokens):
        if token.upper() == "OR":
            # A dangling OR used to turn into a literal ``"or"*`` term and
            # silently returned zero results. Only keep an operator that has
            # a real operand on either side.
            nxt = tokens[i + 1] if i + 1 < len(tokens) else None
            if (
                parts
                and parts[-1] not in ("OR", "AND")
                and nxt is not None
                and nxt.upper() != "OR"
                and not nxt.startswith("-")
            ):
                parts.append("OR")
            continue
        if token.startswith("-") and len(token) > 1:
            term = _term_to_match(token[1:], prefix=True)
            if term:
                parts.append(f"NOT {term}")
            continue
        term = _term_to_match(token, prefix=True)
        if term:
            if parts and parts[-1] != "OR":
                parts.append("AND")
            parts.append(term)

    expression = " ".join(parts).strip()
    # A NOT without a left-hand operand is invalid FTS5 syntax; the engine
    # handles such "exclude only" queries with a dedicated SQL path.
    expression = re.sub(r"^(AND|OR)\s+|\s+(AND|OR)$", "", expression)
    return expression or None


def _term_to_match(token: str, *, prefix: bool) -> str | None:
    if token.startswith('"') and token.endswith('"') and len(token) >= 2:
        inner = token[1:-1].replace('"', '""')
        return f'"{inner}"' if inner else None
    cleaned = token.strip("*").strip("-")
    if not cleaned or not cleaned.strip("_"):
        return None
    cleaned = cleaned.replace('"', '""')
    return f'"{cleaned}"*' if prefix else f'"{cleaned}"'


def _safe_highlight(raw: str | None, pre: str, post: str) -> str:
    """Escape FTS output for HTML, then restore only the trusted markers."""
    if raw is None:
        return ""
    escaped = html.escape(raw, quote=True)
    return escaped.replace(_HL_OPEN, pre).replace(_HL_CLOSE, post)


def _plain_snippet(raw: str | None, limit: int = 240) -> str:
    """HTML-safe preview used when there is no FTS match to highlight."""
    text = html.escape(raw or "", quote=True).replace("\n", " ")
    return text[:limit] + ("…" if len(text) > limit else "")


class SearchEngine:
    """Runs FTS5 queries against the vault and shapes the results."""

    def __init__(self, repo: DocumentRepository) -> None:
        self.repo = repo

    # ------------------------------------------------------------------ API
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
        """Return ranked search results with HTML-safe snippets and total count."""
        match_expr = build_match_query(query)
        if not match_expr:
            return {"query": query, "total": 0, "results": []}

        clauses: list[str] = []
        params: dict[str, Any] = {}
        if content_type:
            clauses.append("d.content_type = :ctype")
            params["ctype"] = content_type
        if tag:
            clauses.append(
                "d.id IN (SELECT dt.document_id FROM document_tags dt"
                " JOIN tags t ON t.id = dt.tag_id WHERE t.name = :tag)"
            )
            params["tag"] = tag
        filters = "".join(f" AND {c}" for c in clauses)

        # ``-spam`` / ``-a -b``: FTS5's NOT is a binary operator and cannot
        # start an expression. Handle it as a set difference instead of
        # letting sqlite3.OperationalError escape as an HTTP 500.
        if match_expr.startswith("NOT "):
            return self._search_exclusions(
                query, match_expr, limit=limit, offset=offset,
                filters=filters, params=params,
            )

        base_sql = f"""
            FROM documents_fts f
            JOIN documents d ON d.id = f.rowid
            WHERE documents_fts MATCH :match AND d.deleted = 0{filters}
        """
        match_params = {**params, "match": match_expr}

        sql = f"""
            SELECT d.id, d.path, d.title, d.content_type, d.modified_at,
                   bm25(documents_fts) AS rank,
                   snippet(documents_fts, 1, :pre, :post, '…', 18) AS snip,
                   highlight(documents_fts, 0, :pre, :post) AS htitle
            {base_sql}
            ORDER BY rank, d.modified_at DESC
            LIMIT :limit OFFSET :offset
        """
        try:
            total = int(self.repo.conn.execute(
                f"SELECT COUNT(*) AS n {base_sql}", match_params
            ).fetchone()["n"])
            rows = self.repo.conn.execute(
                sql, {**match_params, "pre": _HL_OPEN, "post": _HL_CLOSE,
                      "limit": limit, "offset": offset}
            ).fetchall()
        except sqlite3.DatabaseError:
            # Never surface a raw FTS5 syntax error as an HTTP 500. The
            # grammar is deterministic, but hostile input should degrade to
            # "no results" rather than an unhandled exception.
            return {"query": query, "total": 0, "results": []}

        results = [
            SearchResult(
                document_id=row["id"],
                path=row["path"],
                title=row["title"],
                snippet=_safe_highlight(row["snip"], highlight_pre, highlight_post),
                title_highlighted=_safe_highlight(row["htitle"], highlight_pre, highlight_post),
                # FTS5 ranks with *negative* bm25 values; negate so a bigger
                # score is a better match for consumers.
                score=-row["rank"],
                content_type=row["content_type"],
                modified_at=row["modified_at"],
                tags=self.repo.tags_for(row["id"], source="tag"),
            )
            for row in rows
        ]
        return {"query": query, "total": total, "results": results}

    # --------------------------------------------------------------- internal
    def _search_exclusions(
        self,
        query: str,
        match_expr: str,
        *,
        limit: int,
        offset: int,
        filters: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """Answer queries made only of ``-term`` exclusions.

        FTS5 has no "match everything" primitive, so we select documents
        whose rowid is absent from the FTS results for the excluded terms.
        """
        # ``NOT`` clauses are space-separated, not AND-separated.
        excluded_terms = re.findall(r'NOT ("[^"]*"\*?)', match_expr)
        exclude_expr = " OR ".join(excluded_terms)
        if not exclude_expr:
            return {"query": query, "total": 0, "results": []}

        where = f"d.deleted = 0{filters} AND d.id NOT IN (" \
                "SELECT rowid FROM documents_fts WHERE documents_fts MATCH :exclude)"
        query_params = {
            **params, "exclude": exclude_expr, "limit": limit, "offset": offset
        }
        try:
            total = int(self.repo.conn.execute(
                f"SELECT COUNT(*) AS n FROM documents d WHERE {where}", query_params
            ).fetchone()["n"])
            rows = self.repo.conn.execute(
                f"""SELECT d.id, d.path, d.title, d.content_type, d.modified_at,
                           d.content, 0.0 AS rank
                    FROM documents d WHERE {where}
                    ORDER BY d.modified_at DESC NULLS LAST, d.id DESC
                    LIMIT :limit OFFSET :offset""",
                query_params,
            ).fetchall()
        except sqlite3.DatabaseError:
            return {"query": query, "total": 0, "results": []}

        return {
            "query": query,
            "total": total,
            "results": [
                SearchResult(
                    document_id=row["id"],
                    path=row["path"],
                    title=row["title"],
                    snippet=_plain_snippet(row["content"]),
                    title_highlighted=html.escape(row["title"], quote=True),
                    score=0.0,
                    content_type=row["content_type"],
                    modified_at=row["modified_at"],
                    tags=self.repo.tags_for(row["id"], source="tag"),
                )
                for row in rows
            ],
        }

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
