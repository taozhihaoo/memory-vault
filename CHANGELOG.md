# Changelog

All notable changes to MemoryVault are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and the project adheres to [Semantic Versioning](https://semver.org/).

## [1.1.0] — 2026-11-09

A visual overhaul plus a correctness and security hardening pass.

### Added

- **Redesigned dashboard** — new design system (sidebar shell, layered cards,
  gradient accents, iconography, skeletons, micro-animations, responsive
  layout), plus a hand-drawn DPR-aware force-graph canvas with hover tooltips.
- **Bilingual UI** — complete English / 简体中文 dictionaries, a language
  switch, `?lang=` override and `localStorage` persistence.
- **Localized screenshots** — four English and four Chinese captures in
  `docs/screenshots/`, one set per README.
- **Demo tooling** — `scripts/make_demo_vault.py`, `scripts/smoke_cli.py`,
  `scripts/smoke_http.py` and `scripts/check_docs.py`.
- **Frontend test suite** — 18 `node:test` cases for i18n parity, safe
  highlighting, formatting and API URL construction.
- **`python -m memoryvault`** as an alias for the console script.
- **Schema v2** with in-place migration: `document_tags` now keys on
  `(document_id, tag_id, source)`, so a term can be both a tag and a topic.

### Fixed

- Scanning `/docs` no longer marks documents under `/docs-archive` as deleted
  (plain `startswith` prefix matching caused silent data loss).
- Search titles and snippets are HTML-escaped; document content can no longer
  inject markup into the dashboard through `dangerouslySetInnerHTML`.
- Exclusion-only queries (`-spam`) no longer raise an unhandled FTS5 syntax
  error (HTTP 500); dangling `OR` no longer becomes a literal `"or"*` term.
- Sharing one SQLite connection across FastAPI worker threads no longer
  clobbers cursors (random `/api/health` 500s under parallel requests).
- `.log`, `.text` and `.tsv` files are indexed by default — the extension list
  now comes from the parser registry instead of a stale hard-coded set.
- `/api/timeline/events` `total` is an event count, not a document count;
  the activity histogram now filters by calendar days.
- Remembered scan roots make the dashboard **Re-scan vault** button work after
  `memoryvault index <dir>`, even with no watch paths configured.
- CORS is restricted to loopback origins; the SPA static fallback rejects
  path traversal and returns JSON 404 for unknown `/api/*` routes.
- Graph edges no longer dangle when `limit` is used, and `meta.edge_count`
  matches the returned edges.
- CJK keyword extraction produces real words instead of arbitrary 4-character
  chunks; CJK word counts count characters.

### Changed

- `README.md` is the English default; `README.zh-CN.md` is the Chinese
  edition. Security and License sections are written in English in both.
- CI now runs 222 pytest + 18 frontend tests, cross-platform CLI smoke tests,
  README link checks and a richer Docker HTTP smoke test.

## [1.0.0] — 2026-10-02

First stable release.

### Added

- **Document indexing engine** — parsers for TXT, Markdown, PDF, DOCX,
  HTML, JSON and CSV; extraction of title, content, metadata, timestamps
  and SHA-256 hash.
- **Incremental scanner** — watchdog-based file watcher with debounced
  re-indexing; `(size, SHA-256)` change detection; vanished-file handling.
- **Search engine** — SQLite FTS5 inverted index, BM25 ranking, snippet
  and title highlighting, safe prefix/phrase/NOT/OR query grammar,
  vocabulary suggestions.
- **Duplicate detection** — exact SHA-256 duplicate groups and 64-bit
  SimHash near-duplicates with banded candidate lookup.
- **Knowledge graph** — document/tag/topic nodes with `has_tag`,
  `has_topic`, `mentions` (wikilink resolution), `cooccurs` and `similar`
  edges; neighborhood queries.
- **Timeline** — append-only event log, per-document history, per-day and
  per-month activity aggregation.
- **Web interface** — FastAPI backend and React dashboard with Search,
  Document viewer, Graph and Timeline views.
- **Optional AI plugin interfaces** — `EmbeddingProvider` and
  `SummaryProvider` abstractions with local, deterministic reference
  implementations. No external AI calls anywhere.
- **CLI** — `index`, `watch`, `search`, `show`, `stats`, `tags`,
  `duplicates`, `graph`, `timeline`, `serve`, `scan`.
- **Quality** — 192 pytest tests, Docker image, docker-compose, GitHub
  Actions CI (3 OSes × 2 Python versions + frontend + Docker smoke test),
  architecture documentation, MIT license.
