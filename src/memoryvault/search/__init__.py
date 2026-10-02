"""FTS5-powered keyword search with BM25 ranking and snippet highlighting."""

from memoryvault.search.engine import SearchEngine, build_match_query

__all__ = ["SearchEngine", "build_match_query"]
