import React, { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api, fmtNumber } from "../api.js";
import { useI18n } from "../locale.jsx";
import {
  Chip, EmptyState, ErrorBox, Highlight, Icon, LoadingState, TypeBadge,
} from "../components.jsx";

export default function SearchPage() {
  const { lang, t } = useI18n();
  const [params, setParams] = useSearchParams();
  const query = params.get("q") ?? "";
  const tagFilter = params.get("tag") ?? "";
  const typeFilter = params.get("type") ?? "";

  const [input, setInput] = useState(query);
  const [state, setState] = useState({ loading: false, data: null, error: null });
  const [tags, setTags] = useState([]);
  const [suggestions, setSuggestions] = useState([]);
  const [showSuggest, setShowSuggest] = useState(false);
  const inputRef = useRef(null);

  useEffect(() => {
    api.tags().then(setTags).catch(() => setTags([]));
  }, []);

  const runSearch = React.useCallback((q, tag, type) => {
    if (!q.trim()) {
      setState({ loading: false, data: null, error: null });
      return () => {};
    }
    let cancelled = false;
    setState((s) => ({ ...s, loading: true, error: null }));
    api
      .search(q, { limit: 30, tag, content_type: type })
      .then((data) => !cancelled && setState({ loading: false, data, error: null }))
      .catch((err) => !cancelled && setState({ loading: false, data: null, error: err.message }));
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    setInput(query);
    return runSearch(query, tagFilter, typeFilter);
  }, [query, tagFilter, typeFilter, runSearch]);

  useEffect(() => {
    if (input.trim().length < 2) {
      setSuggestions([]);
      return;
    }
    const handle = setTimeout(() => {
      api
        .suggest(input.trim())
        .then((res) => {
          setSuggestions(res.suggestions.slice(0, 6));
          // Only open the dropdown while the user is actually typing; a
          // pre-filled ?q= URL must not leave it hanging over the results.
          if (document.activeElement === inputRef.current) setShowSuggest(true);
        })
        .catch(() => setSuggestions([]));
    }, 180);
    return () => clearTimeout(handle);
  }, [input]);

  // "/" focuses search from anywhere except while typing in a field.
  useEffect(() => {
    function onKeyDown(event) {
      const target = event.target;
      const typing = target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable);
      if (event.key === "/" && !typing) {
        event.preventDefault();
        inputRef.current?.focus();
      }
      if (event.key === "Escape") {
        setShowSuggest(false);
        inputRef.current?.blur();
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  function commit(nextQuery) {
    setShowSuggest(false);
    setSuggestions([]);
    const next = new URLSearchParams();
    if (nextQuery.trim()) next.set("q", nextQuery.trim());
    if (tagFilter) next.set("tag", tagFilter);
    if (typeFilter) next.set("type", typeFilter);
    setParams(next);
  }

  function submit(event) {
    event.preventDefault();
    commit(input);
  }

  function setFilter(key, value) {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    setParams(next);
  }

  const { loading, data, error } = state;
  const total = data?.total ?? 0;

  return (
    <div className="page search-page">
      <div className="search-hero">
        <div className="eyebrow"><Icon name="sparkles" size={13} />{t("search.eyebrow")}</div>
        <h1>{t("search.title")}</h1>
        <p>{t("search.subtitle")}</p>
      </div>

      <form className="search-box" onSubmit={submit} role="search">
        <span className="search-icon"><Icon name="search" size={20} /></span>
        <input
          ref={inputRef}
          value={input}
          placeholder={t("search.placeholder")}
          aria-label={t("search.title")}
          autoComplete="off"
          onChange={(e) => setInput(e.target.value)}
          onFocus={() => suggestions.length && setShowSuggest(true)}
          onBlur={() => setShowSuggest(false)}
        />
        <kbd className="search-kbd">/</kbd>
        <button type="submit" className="btn primary" disabled={loading}>
          {loading ? <span className="spinner light" /> : <Icon name="search" size={16} />}
          {loading ? t("search.searching") : t("search.button")}
        </button>
        {showSuggest && suggestions.length > 0 && (
          <ul className="suggest">
            {suggestions.map((s) => (
              <li
                key={s.term}
                onMouseDown={(e) => {
                  e.preventDefault();
                  setInput(s.term);
                  commit(s.term);
                }}
              >
                <Icon name="hash" size={14} />
                <span className="suggest-term">{s.term}</span>
                <span className="suggest-count">
                  {fmtNumber(s.documents, lang)} {s.documents === 1 ? t("search.suggestDoc") : t("search.suggestDocs")}
                </span>
              </li>
            ))}
          </ul>
        )}
      </form>
      <div className="search-grammar"><Icon name="info" size={13} />{t("search.grammar")}</div>

      {(tags.length > 0 || data) && (
        <div className="filters">
          <span className="filters-label"><Icon name="tag" size={14} />{t("search.tagFilter")}</span>
          <Chip active={!tagFilter} onClick={() => setFilter("tag", "")}>{t("common.all")}</Chip>
          {tags.slice(0, 12).map((tag) => (
            <Chip
              key={tag.name}
              active={tagFilter === tag.name}
              onClick={() => setFilter("tag", tag.name === tagFilter ? "" : tag.name)}
            >
              {tag.name}<span className="chip-count">{fmtNumber(tag.document_count, lang)}</span>
            </Chip>
          ))}
        </div>
      )}

      {error && <ErrorBox message={`${t("search.failed")}: ${error}`} onRetry={() => commit(query || input)} retryLabel={t("common.retry")} />}

      {loading && !data && <LoadingState label={t("search.searching")} cards={4} />}

      {data && (
        <div className="results">
          <div className="results-meta">
            <strong>{fmtNumber(total, lang)}</strong> {total === 1 ? t("search.oneUnit") : t("search.docsUnit")}
            {data.took_ms != null && <span className="results-time">· {data.took_ms.toFixed(1)} ms</span>}
          </div>
          {data.results.map((hit, index) => (
            <Link to={`/doc/${hit.document_id}`} className="result-card" key={hit.document_id}>
              <div className="result-rank">{String(index + 1).padStart(2, "0")}</div>
              <div className="result-body">
                <div className="result-title"><Highlight html={hit.title_highlighted || hit.title} /></div>
                <div className="result-snippet"><Highlight html={hit.snippet} /></div>
                <div className="result-meta">
                  <TypeBadge type={hit.content_type} />
                  <span className="result-path" title={hit.path}><Icon name="folder" size={13} />{hit.path}</span>
                  {Array.isArray(hit.tags) && hit.tags.length > 0 && (
                    <span className="result-tags"><Icon name="tag" size={13} />{hit.tags.join(", ")}</span>
                  )}
                  <span className="score" title={t("search.score")}>
                    <Icon name="zap" size={13} />{(hit.score ?? 0).toFixed(2)}
                  </span>
                </div>
              </div>
              <Icon name="arrowRight" size={16} className="result-arrow" />
            </Link>
          ))}
          {total === 0 && (
            <EmptyState icon="search" title={t("search.noResultsTitle")} body={t("search.noResultsBody")} />
          )}
        </div>
      )}

      {!data && !error && !loading && (
        <EmptyState
          icon="database"
          title={t("search.emptyTitle")}
          body={t("search.emptyBody")}
          action={<span className="shortcut-hint"><kbd>/</kbd> {t("search.shortcut")}</span>}
        />
      )}
    </div>
  );
}
