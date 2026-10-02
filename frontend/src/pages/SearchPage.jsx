import React, { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../api.js";

export default function SearchPage() {
  const [params, setParams] = useSearchParams();
  const query = params.get("q") ?? "";
  const tagFilter = params.get("tag") ?? "";
  const typeFilter = params.get("type") ?? "";

  const [input, setInput] = useState(query);
  const [state, setState] = useState({ loading: false, data: null, error: null });
  const [tags, setTags] = useState([]);
  const [suggestions, setSuggestions] = useState([]);
  const inputRef = useRef(null);

  useEffect(() => {
    api.tags().then(setTags).catch(() => setTags([]));
  }, []);

  useEffect(() => {
    setInput(query);
    if (!query.trim()) {
      setState({ loading: false, data: null, error: null });
      return;
    }
    let cancelled = false;
    setState((s) => ({ ...s, loading: true }));
    api
      .search(query, { limit: 30, tag: tagFilter, content_type: typeFilter })
      .then((data) => !cancelled && setState({ loading: false, data, error: null }))
      .catch((err) => !cancelled && setState({ loading: false, data: null, error: err.message }));
    return () => {
      cancelled = true;
    };
  }, [query, tagFilter, typeFilter]);

  useEffect(() => {
    if (input.trim().length < 2) {
      setSuggestions([]);
      return;
    }
    const handle = setTimeout(() => {
      api
        .suggest(input.trim())
        .then((res) => setSuggestions(res.suggestions.slice(0, 6)))
        .catch(() => setSuggestions([]));
    }, 200);
    return () => clearTimeout(handle);
  }, [input]);

  function submit(e) {
    e.preventDefault();
    setSuggestions([]);
    const next = new URLSearchParams();
    if (input.trim()) next.set("q", input.trim());
    if (tagFilter) next.set("tag", tagFilter);
    if (typeFilter) next.set("type", typeFilter);
    setParams(next);
  }

  function setFilter(key, value) {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    setParams(next);
  }

  const { loading, data, error } = state;

  return (
    <div className="page search-page">
      <form className="search-box" onSubmit={submit}>
        <input
          ref={inputRef}
          autoFocus
          value={input}
          placeholder='Search your memory… (prefix matching, "quoted phrases", -exclude, OR)'
          onChange={(e) => setInput(e.target.value)}
        />
        <button type="submit" disabled={loading}>
          {loading ? "Searching…" : "Search"}
        </button>
        {suggestions.length > 0 && (
          <ul className="suggest">
            {suggestions.map((s) => (
              <li
                key={s.term}
                onMouseDown={() => {
                  setInput(s.term);
                  setSuggestions([]);
                  const next = new URLSearchParams();
                  next.set("q", s.term);
                  setParams(next);
                }}
              >
                {s.term} <span className="muted">· {s.documents} docs</span>
              </li>
            ))}
          </ul>
        )}
      </form>

      {(tags.length > 0 || data) && (
        <div className="filters">
          <span className="muted">tag:</span>
          <button className={!tagFilter ? "chip active" : "chip"} onClick={() => setFilter("tag", "")}>
            all
          </button>
          {tags.slice(0, 12).map((t) => (
            <button
              key={t.name}
              className={tagFilter === t.name ? "chip active" : "chip"}
              onClick={() => setFilter("tag", t.name === tagFilter ? "" : t.name)}
            >
              {t.name} <span className="chip-count">{t.document_count}</span>
            </button>
          ))}
        </div>
      )}

      {error && <div className="error-box">Search failed: {error}</div>}

      {data && (
        <div className="results">
          <div className="results-meta muted">
            {data.total} result{data.total === 1 ? "" : "s"}
            {data.took_ms != null && <> · {data.took_ms.toFixed(1)} ms</>}
          </div>
          {data.results.map((hit) => (
            <Link to={`/doc/${hit.document_id}`} className="result-card" key={hit.document_id}>
              <div className="result-title" dangerouslySetInnerHTML={{ __html: hit.title_highlighted }} />
              <div className="result-snippet" dangerouslySetInnerHTML={{ __html: hit.snippet }} />
              <div className="result-meta muted">
                <span className="score" title="BM25 score">score {hit.score.toFixed(2)}</span>
                <span>{hit.content_type}</span>
                <span className="result-path">{hit.path}</span>
                {hit.tags.length > 0 && <span className="tags-inline">{hit.tags.join(", ")}</span>}
              </div>
            </Link>
          ))}
          {data.total === 0 && (
            <div className="empty">Nothing found. Try fewer words or a shorter prefix.</div>
          )}
        </div>
      )}

      {!data && !error && (
        <div className="empty hero">
          <h2>Search everything you've ever indexed</h2>
          <p>
            Deterministic full-text search powered by SQLite FTS5 with BM25 ranking.
            No AI required, no cloud involved.
          </p>
        </div>
      )}
    </div>
  );
}
