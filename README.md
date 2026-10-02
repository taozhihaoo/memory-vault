# MemoryVault

> A local-first personal knowledge management and digital memory engine.
> Index, organize, search and visualize your documents — **completely offline**.

[![CI](https://img.shields.io/badge/CI-GitHub_Actions-blue)](.github/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue)](pyproject.toml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-192%20passing-brightgreen)](tests/)

MemoryVault turns a folder of documents into a searchable, cross-linked
knowledge base: full-text search with BM25 ranking, duplicate detection,
an interactive knowledge graph and an activity timeline — all backed by a
single SQLite file on your own disk.

**Core principles**

1. **Local-first** — all data stays on your machine. No external API calls,
   no telemetry, no cloud. Ever.
2. **Deterministic core** — parsing, indexing and search work without AI.
3. **AI is an optional extension** — clean plugin interfaces exist
   (`EmbeddingProvider`, `SummaryProvider`), but none ship with network calls.

---

## Feature overview

| Phase | Capability | Where |
|-------|------------|-------|
| 1 | Parsers for TXT, Markdown, PDF, DOCX, HTML, JSON, CSV — extracting title, content, metadata, timestamps and SHA-256 hash | `src/memoryvault/parser/` |
| 2 | Incremental scanner: file watcher, hash-based change detection, re-index only what changed, delete what vanished | `src/memoryvault/indexer/scanner.py` |
| 3 | SQLite FTS5 search: inverted index, BM25 ranking, snippets with `<mark>` highlighting, prefix/phrase/NOT/OR query grammar | `src/memoryvault/search/` |
| 4 | Duplicate detection: exact SHA-256 groups + 64-bit SimHash near-duplicates with banded candidate lookup | `src/memoryvault/dedup/` |
| 5 | Knowledge graph: document/tag/topic nodes, `mentions` (wikilinks), `cooccurs`, `similar` edges | `src/memoryvault/graph/` |
| 6 | Timeline: append-only event log, per-document history, activity histogram | `src/memoryvault/timeline/` |
| 7 | React dashboard: Search, Document viewer, Graph, Timeline, Dashboard | `frontend/` |
| 8 | Optional AI plugin interfaces (abstractions only — no external calls) | `src/memoryvault/ai/` |

## Architecture

```
                        ┌──────────────────────────────────────────────┐
                        │                 React dashboard              │
                        │   Search │ Document viewer │ Graph │ Timeline│
                        └───────────────────────┬──────────────────────┘
                                                │ HTTP (localhost only)
                        ┌───────────────────────▼──────────────────────┐
                        │              FastAPI application             │
                        │  /api/search /api/documents /api/graph       │
                        │  /api/timeline /api/duplicates /api/scan     │
                        └───────┬───────────────┬──────────────┬───────┘
                                │               │              │
                 ┌──────────────▼───┐   ┌───────▼──────┐  ┌────▼─────────┐
                 │   Search engine  │   │ Graph builder│  │  Timeline    │
                 │  FTS5 + BM25     │   │ nodes/edges  │  │  service     │
                 └──────────────┬───┘   └───────┬──────┘  └────┬─────────┘
                                │               │              │
┌──────────────┐   ┌────────────▼───────────────▼──────────────▼─────────┐
│ File system  │   │              DocumentRepository (SQLite)            │
│ TXT/MD/PDF/  ├──►│  documents │ documents_fts │ tags │ events │ bands  │
│ DOCX/HTML/   │   └────────────────────────────▲────────────────────────┘
│ JSON/CSV     │                                │
└──────┬───────┘                 ┌──────────────┴──────────────┐
       │                         │        Index engine         │
┌──────▼───────┐                 │  parse → hash → simhash →   │
│ Incremental  ├────────────────►│  keywords → upsert          │
│ scanner +    │                 └──────────────┬──────────────┘
│ watcher      │                                │
└──────────────┘                  ┌─────────────▼─────────────┐
                                  │  Optional AI providers    │
                                  │  (Embedding / Summary)    │
                                  │  abstractions only —      │
                                  │  no network calls shipped │
                                  └───────────────────────────┘
```

The same diagram as rendered Mermaid lives in
[docs/architecture.md](docs/architecture.md).

### Data flow

1. The **incremental scanner** walks configured directories, skipping
   unchanged files via `(size, SHA-256)` comparison.
2. The **index engine** parses each changed file, computes content hashes and
   a SimHash fingerprint, extracts deterministic keyword topics, and upserts
   the document atomically (tables + FTS5 + tags + event log).
3. **Search** translates user queries into safe FTS5 `MATCH` expressions and
   returns BM25-ranked results with highlighted snippets.
4. The **graph builder** materializes documents/tags/topics and relationships
   on demand — no separate graph database required.
5. The React dashboard talks to the FastAPI server on `127.0.0.1` only.

## Quick start

### pip

```bash
pip install -e .

memoryvault index ~/Documents/notes          # one-shot incremental index
memoryvault search "neural networks"          # ranked keyword search
memoryvault watch ~/Documents/notes           # live re-indexing on change
memoryvault stats                             # vault statistics
memoryvault duplicates                        # exact + near duplicates
memoryvault graph --out graph.json            # export knowledge graph
memoryvault serve                             # API + dashboard on :8000
```

The default vault lives at `~/.memoryvault/memoryvault.db`
(override with `MEMORYVAULT_HOME` or `--db`).

### Docker

```bash
docker compose up --build
# open http://127.0.0.1:8000 — the dashboard with sample documents
```

The compose file mounts `examples/sample-docs` read-only at `/docs` and keeps
the SQLite vault in a named volume.

### Frontend development

```bash
cd frontend
npm install
npm run dev          # vite dev server on :5173, proxying /api to :8000
npm run build        # production bundle in frontend/dist
```

`memoryvault serve` automatically serves `frontend/dist` when it exists.

## Python API

```python
from memoryvault import Vault

with Vault.open("my-vault.db") as vault:
    vault.index("notes/")                          # incremental
    hits = vault.search.search("quantum")          # BM25-ranked
    graph = vault.graph.build()                    # nodes + edges
    dups = vault.dedup.find_all()                  # exact + similar
    history = vault.timeline.document_history(1)   # one document's events
```

Every subsystem is usable standalone — the API layer is a thin wrapper.

## Optional AI extensions

MemoryVault never calls external services. Applications that embed it can
register providers for semantic search or summarization:

```python
from memoryvault.ai import Registry, HashingEmbeddingProvider, NullSummaryProvider

registry = Registry()
registry.register_embedding(HashingEmbeddingProvider(dimension=256), default=True)
registry.register_summary(NullSummaryProvider())

vectors = registry.embedding().embed(["some document text"])
summary = registry.summary().summarize(long_text, max_length=280)
```

The two shipped implementations are local and deterministic (feature hashing
and extractive truncation) — they exist to define the contract, not to call
out to a model. Plug in a local model runner (e.g. ONNX) by implementing
`EmbeddingProvider` / `SummaryProvider`.

## Configuration

| Option | Default | Meaning |
|--------|---------|---------|
| `MEMORYVAULT_HOME` | `~/.memoryvault` | Directory holding `memoryvault.db` |
| `MEMORYVAULT_API_HOST` | `127.0.0.1` | Bind address for `serve` (containers use `0.0.0.0`) |
| `MEMORYVAULT_API_PORT` | `8000` | Port for `serve` |
| `--db PATH` | — | Explicit vault file location |
| `max_file_size` | 64 MiB | Files above are skipped |
| `simhash_threshold` | 12 | Hamming distance for near-duplicates |
| `topics_per_document` | 8 | Auto-extracted keywords per document |
| `watcher_debounce_seconds` | 1.0 | Settle time before a watcher re-scan |

## Supported formats

| Format | Extensions | Title source | Metadata |
|--------|-----------|--------------|----------|
| Plain text | `.txt` `.log` | first line | — |
| Markdown | `.md` `.markdown` | frontmatter → `#` heading | frontmatter, tags, wikilinks, headings |
| PDF | `.pdf` | docinfo → first line | author/subject, page count |
| Word | `.docx` | core properties → first paragraph | author, headings |
| HTML | `.html` `.htm` | `<title>` → `<h1>` | meta tags, headings |
| JSON | `.json` | `title`/`name` key | declared keys, tags |
| CSV/TSV | `.csv` `.tsv` | file name | columns, row count, delimiter |

## Testing

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

192 tests cover parsing, indexing, incremental scanning, search ranking and
highlighting, database integrity, duplicate detection, the knowledge graph,
the timeline, the HTTP API and the CLI — across Linux, macOS and Windows in
CI.

## Project layout

```
memoryvault/
├── src/memoryvault/
│   ├── parser/        # format parsers (TXT, MD, PDF, DOCX, HTML, JSON, CSV)
│   ├── indexer/       # index engine + incremental scanner + file watcher
│   ├── search/        # FTS5 search engine, query builder, BM25, snippets
│   ├── database/      # schema, connection, document repository
│   ├── graph/         # knowledge-graph builder
│   ├── dedup/         # SimHash + duplicate detector
│   ├── timeline/      # activity and document history
│   ├── api/           # FastAPI application
│   ├── ai/            # optional provider abstractions (no network calls)
│   ├── vault.py       # facade wiring every subsystem together
│   └── cli.py         # `memoryvault` command-line interface
├── frontend/          # React dashboard (Vite)
├── tests/             # 192 pytest tests
├── examples/sample-docs/
├── docs/architecture.md
├── Dockerfile · docker-compose.yml · .github/workflows/ci.yml
└── LICENSE (MIT)
```

## Roadmap ideas

* Semantic search wired to the `EmbeddingProvider` interface (local models only)
* Annotation and highlighting inside the document viewer
* Export to static site / Obsidian vault
* Attachment and image OCR indexing

## Contributing

Issues and pull requests welcome. Please run `pytest` and `npm run build`
before submitting; CI enforces both plus a Docker smoke test.

## License

[MIT](LICENSE) — © 2026 MemoryVault Contributors
