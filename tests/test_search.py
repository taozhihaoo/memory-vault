"""Search engine tests: query building, BM25 ranking, highlighting, filters."""

from __future__ import annotations

from pathlib import Path

from memoryvault.search.engine import SearchEngine, build_match_query


# --------------------------------------------------------- query building
def test_simple_term_becomes_prefix_query():
    assert build_match_query("hello") == '"hello"*'


def test_multiple_terms_are_anded():
    assert build_match_query("hello world") == '"hello"* AND "world"*'


def test_quoted_phrase_is_exact():
    assert build_match_query('"neural networks"') == '"neural networks"'


def test_negation():
    # FTS5's NOT is binary: "a NOT b"
    assert build_match_query("good -bad") == '"good"* NOT "bad"*'


def test_or_operator_preserved():
    query = build_match_query("cats OR dogs")
    assert query == '"cats"* OR "dogs"*'


def test_empty_and_stopword_queries_return_none():
    assert build_match_query("") is None
    assert build_match_query("   ") is None
    assert build_match_query('""') is None
    assert build_match_query("---") is None


def test_fts_special_characters_are_escaped():
    import sqlite3

    expr = build_match_query('hello "world OR (nested)')
    assert expr  # a safe expression is produced
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE VIRTUAL TABLE t USING fts5(x)")
    conn.execute('INSERT INTO t VALUES ("hello colon world")')
    # must not raise: the hostile input is neutralized by quoting
    conn.execute(f"SELECT * FROM t WHERE t MATCH '{expr}'")


def test_hyphen_only_prefix():
    assert build_match_query("-spam") == 'NOT "spam"*'


# ----------------------------------------------------------------- ranking
def test_search_finds_matching_documents(indexed_vault):
    found = indexed_vault.search.search("machine learning")
    assert found["total"] >= 2
    titles = {h.title for h in found["results"]}
    assert "Beta Notes" in titles


def test_search_empty_query_returns_empty(indexed_vault):
    assert indexed_vault.search.search('"" ')["total"] == 0


def test_search_no_match(indexed_vault):
    found = indexed_vault.search.search("zzzqqqxxx")
    assert found["total"] == 0 and found["results"] == []


def test_bm25_ranks_relevant_document_first(indexed_vault):
    # quantum.html is entirely about quantum computing; others only mention it
    found = indexed_vault.search.search("quantum qubits")
    assert found["results"], "expected at least one hit"
    assert found["results"][0].title == "Quantum Computing"
    assert found["results"][0].score > 0


def test_search_scores_are_positive_and_sorted(indexed_vault):
    found = indexed_vault.search.search("learning")
    scores = [h.score for h in found["results"]]
    assert all(s > 0 for s in scores)
    assert scores == sorted(scores, reverse=True)


def test_search_highlights_snippet(indexed_vault):
    found = indexed_vault.search.search("transformative")
    hit = found["results"][0]
    assert "<mark>transformative</mark>" in hit.snippet


def test_search_highlights_title(indexed_vault):
    found = indexed_vault.search.search("Beta")
    hit = found["results"][0]
    assert "<mark>Beta</mark>" in hit.title_highlighted


def test_custom_highlight_markers(indexed_vault):
    found = indexed_vault.search.search("beta", highlight_pre="[", highlight_post="]")
    assert "[beta]" in found["results"][0].snippet.lower()


def test_search_prefix_matches_partial_words(indexed_vault):
    found = indexed_vault.search.search("quant")  # prefix of quantum
    assert found["total"] >= 1


def test_search_phrase_query(indexed_vault):
    found = indexed_vault.search.search('"neural networks"')
    # both beta copies contain the phrase
    assert found["total"] == 2
    assert {h.title for h in found["results"]} == {"Beta Notes"}


def test_search_negation_excludes(indexed_vault):
    without = indexed_vault.search.search("learning -machine")
    with_machine = indexed_vault.search.search("learning machine")
    assert 0 < without["total"] < with_machine["total"]


def test_search_filter_by_content_type(indexed_vault):
    found = indexed_vault.search.search("greenhouse", content_type="json")
    assert found["total"] == 1
    assert found["results"][0].content_type == "json"


def test_search_filter_by_tag(indexed_vault):
    found = indexed_vault.search.search("greenhouse", tag="iot")
    assert found["total"] == 1


def test_search_results_carry_tags(indexed_vault):
    found = indexed_vault.search.search("greenhouse deployment")
    json_hits = [h for h in found["results"] if h.content_type == "json"]
    assert json_hits and "iot" in json_hits[0].tags


def test_search_pagination(indexed_vault):
    page1 = indexed_vault.search.search("learning", limit=1, offset=0)
    page2 = indexed_vault.search.search("learning", limit=1, offset=1)
    assert page1["results"] and page2["results"]
    assert page1["results"][0].document_id != page2["results"][0].document_id


# ---------------------------------------------------------------- suggest
def test_suggest_returns_vocabulary(indexed_vault):
    suggestions = indexed_vault.search.suggest("quan")
    assert suggestions and suggestions[0]["term"].startswith("quan")


def test_suggest_rejects_weird_input(indexed_vault):
    assert indexed_vault.search.suggest("") == []
    assert indexed_vault.search.suggest("a;b-- DROP") == []


# --------------------------------------------------------------- more-like
def test_more_like_returns_related(indexed_vault):
    beta = indexed_vault.repo.get_by_path(Path("beta-notes.md"), include_deleted=False) \
        if False else None
    docs = indexed_vault.repo.list_documents(limit=100)
    beta = next(d for d in docs if d.title == "Beta Notes")
    related = indexed_vault.search.more_like(beta.id, limit=5)
    assert isinstance(related, list)
    assert all(r.document_id != beta.id for r in related)
