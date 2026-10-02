# Architecture

MemoryVault is a single-user, single-process application with an optional
HTTP surface. Everything below runs on one machine with no network egress.

## Rendered diagram

```mermaid
flowchart TB
    subgraph FS["File system"]
        F["TXT · MD · PDF · DOCX · HTML · JSON · CSV"]
    end

    subgraph Scanner["Incremental scanner"]
        W["watchdog file watcher<br/>(debounced events)"]
        HC[("size + SHA-256<br/>change detection")]
    end

    subgraph Engine["Index engine"]
        P["format parsers<br/>title · content · metadata<br/>timestamps · hash"]
        SH["SimHash fingerprint"]
        KW["keyword topics<br/>(deterministic TF)"]
    end

    subgraph DB[("SQLite vault file")]
        D[("documents")]
        FTS[("documents_fts<br/>FTS5 inverted index")]
        T[("tags / document_tags")]
        E[("document_events")]
        B[("simhash_bands")]
    end

    subgraph Query["Query layer"]
        SE["Search engine<br/>safe MATCH builder · BM25 · snippets"]
        GB["Graph builder<br/>documents · tags · topics<br/>mentions · cooccurs · similar"]
        TL["Timeline service<br/>history · activity buckets"]
        DD["Duplicate detector<br/>exact + near"]
    end

    subgraph HTTP["FastAPI (127.0.0.1)"]
        API["/api/search · /api/documents<br/>/api/graph · /api/timeline<br/>/api/duplicates · /api/scan"]
    end

    UI["React dashboard<br/>Search · Viewer · Graph · Timeline"]
    AI["Optional AI providers<br/>(Embedding / Summary interfaces)<br/>no network calls shipped"]

    F --> W --> HC
    F --> HC
    HC --> "changed files only" P
    P --> SH --> B
    P --> KW --> T
    P --> D
    P --> FTS
    D --> E

    D --> GB
    T --> GB
    B --> DD
    FTS --> SE
    E --> TL

    SE --> API
    GB --> API
    TL --> API
    DD --> API
    API --> UI
    AI -.-> Engine
```

## Design decisions

### One SQLite file is the whole system

Documents, the FTS5 inverted index, tags, the event log and SimHash bands
all live in one database. Backing up the vault *is* copying one file.
FTS5's external-content-free standalone table (`documents_fts`) is maintained
inside the repository's write path, so the inverted index can never drift
from the document table.

### Deterministic core

Parsing, hashing, SimHash, keyword extraction and BM25 ranking are pure
functions of file bytes. The same input always produces the same vault state
— no model inference anywhere in the core, no randomness (even the graph
layout uses a seeded PRNG), no time-dependent scoring.

### Incremental by construction

Every file is fingerprinted with SHA-256. Scans compare `(size, hash)` against
stored state and only re-parse files that actually changed; vanished files are
marked deleted (and purgeable) rather than silently dropped, so the timeline
records the removal.

### Safe search grammar

User queries are translated, never concatenated raw, into FTS5 `MATCH`
expressions: bare words become quoted prefix terms (`"hello"*`), quotes mark
phrases, `-term` becomes `NOT`, uppercase `OR` is honored. Malformed or
hostile input degrades to a quoted literal — it cannot break out of the
grammar.

### Duplicates without pairwise scans at scale

Near-duplicate lookup first consults the `simhash_bands` table (4 × 16-bit
bands of each 64-bit fingerprint): only documents sharing at least one band
are candidates for a full Hamming-distance check.

### The graph is a view, not a store

`GraphBuilder` materializes nodes/edges from the relational tables on
request. It stays consistent with the documents automatically and its size
is bounded by configurable caps (topics per document, tag co-occurrence).

### HTTP is optional and local

The FastAPI app binds `127.0.0.1` by default, serves the prebuilt React
bundle as static files (SPA fallback), and exists only for convenience —
the CLI uses the same Python interfaces directly.

## Extension points

| Interface | Purpose | Shipped implementation |
|-----------|---------|------------------------|
| `EmbeddingProvider` | vectors for semantic search | `HashingEmbeddingProvider` (local, deterministic) |
| `SummaryProvider` | document summaries | `NullSummaryProvider` (extractive) |

Both plug into `memoryvault.ai.Registry`; no implementation in this
repository performs network I/O.
