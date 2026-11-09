"""Database schema (versioned, idempotent, upgradeable)."""

from __future__ import annotations

import sqlite3

#: v2 — ``document_tags`` primary key includes ``source`` so one term can be
#: both an explicit tag and an auto-extracted topic on the same document.
SCHEMA_VERSION = 2

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- ---------------------------------------------------------------- documents
CREATE TABLE IF NOT EXISTS documents (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    path          TEXT    NOT NULL UNIQUE,
    title         TEXT    NOT NULL DEFAULT '',
    content       TEXT    NOT NULL DEFAULT '',
    content_type  TEXT    NOT NULL DEFAULT '',
    file_size     INTEGER NOT NULL DEFAULT 0,
    sha256        TEXT    NOT NULL,
    simhash       TEXT,
    metadata      TEXT    NOT NULL DEFAULT '{}',
    word_count    INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT,
    modified_at   TEXT,
    indexed_at    TEXT    NOT NULL,
    deleted       INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_documents_sha256  ON documents(sha256);
CREATE INDEX IF NOT EXISTS idx_documents_simhash ON documents(simhash);
CREATE INDEX IF NOT EXISTS idx_documents_modified ON documents(modified_at);

-- --------------------------------------------------------------------- tags
CREATE TABLE IF NOT EXISTS tags (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS document_tags (
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    tag_id      INTEGER NOT NULL REFERENCES tags(id)      ON DELETE CASCADE,
    source      TEXT    NOT NULL DEFAULT 'auto',
    PRIMARY KEY (document_id, tag_id, source)
);

CREATE INDEX IF NOT EXISTS idx_document_tags_tag ON document_tags(tag_id);

-- ------------------------------------------------------------------- events
CREATE TABLE IF NOT EXISTS document_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER REFERENCES documents(id) ON DELETE SET NULL,
    path        TEXT NOT NULL,
    event_type  TEXT NOT NULL,
    title       TEXT NOT NULL DEFAULT '',
    detail      TEXT NOT NULL DEFAULT '',
    occurred_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_events_time   ON document_events(occurred_at);
CREATE INDEX IF NOT EXISTS idx_events_doc    ON document_events(document_id);

-- ------------------------------------------------------- simhash candidate bands
CREATE TABLE IF NOT EXISTS simhash_bands (
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    band_index  INTEGER NOT NULL,
    band_value  INTEGER NOT NULL,
    PRIMARY KEY (document_id, band_index)
);

CREATE INDEX IF NOT EXISTS idx_bands_value ON simhash_bands(band_index, band_value);

-- --------------------------------------------------------------- settings
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

# The FTS5 table is created separately because the tokenizer option is not
# valid inside the shared script for older SQLite builds; keep it explicit.
_FTS_SQL = """
CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
    title,
    content,
    tokenize = 'unicode61 remove_diacritics 2'
);
"""

_V2_MIGRATION = """
-- v1 used PRIMARY KEY (document_id, tag_id), which silently discarded a
-- topic whenever the same word was also an explicit tag. Rebuild the link
-- table with source as part of the key; all existing rows are preserved.
CREATE TABLE IF NOT EXISTS document_tags_v2 (
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    tag_id      INTEGER NOT NULL REFERENCES tags(id)      ON DELETE CASCADE,
    source      TEXT    NOT NULL DEFAULT 'auto',
    PRIMARY KEY (document_id, tag_id, source)
);
INSERT OR IGNORE INTO document_tags_v2 (document_id, tag_id, source)
    SELECT document_id, tag_id, source FROM document_tags;
DROP TABLE document_tags;
ALTER TABLE document_tags_v2 RENAME TO document_tags;
CREATE INDEX IF NOT EXISTS idx_document_tags_tag ON document_tags(tag_id);
"""


def _upgrade(conn: sqlite3.Connection, from_version: int) -> None:
    """Apply forward migrations for vaults created by older releases."""
    if from_version < 2:
        # Rebuilding a link table requires temporarily relaxing FK checks:
        # legacy vaults may contain rows whose parents were pruned.
        conn.execute("PRAGMA foreign_keys=OFF")
        try:
            conn.executescript(_V2_MIGRATION)
        finally:
            conn.execute("PRAGMA foreign_keys=ON")
            conn.commit()


def apply_schema(conn: sqlite3.Connection) -> None:
    """Create/upgrade every table and record the current schema version."""
    conn.executescript(_SCHEMA_SQL)
    conn.executescript(_FTS_SQL)
    row = conn.execute(
        "SELECT value FROM schema_meta WHERE key = 'schema_version'"
    ).fetchone()
    if row is None:
        conn.execute(
            "INSERT INTO schema_meta (key, value) VALUES ('schema_version', ?)",
            (str(SCHEMA_VERSION),),
        )
    else:
        current = int(row["value"])
        if current < SCHEMA_VERSION:
            _upgrade(conn, current)
            conn.execute(
                "UPDATE schema_meta SET value = ? WHERE key = 'schema_version'",
                (str(SCHEMA_VERSION),),
            )
    conn.commit()
