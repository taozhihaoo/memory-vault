# Changelog

All notable changes to MemoryVault are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and the project adheres to [Semantic Versioning](https://semver.org/).

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
