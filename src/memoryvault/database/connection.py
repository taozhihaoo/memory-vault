"""SQLite connection management.

The whole engine runs on a single SQLite database file. Connections use WAL
journaling so the API server and the file watcher can share the database
without blocking each other.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from memoryvault.database.schema import SCHEMA_VERSION, apply_schema


def connect(db_path: str | Path, *, read_only: bool = False) -> sqlite3.Connection:
    """Open (and initialise) the MemoryVault database.

    Parameters
    ----------
    db_path:
        Filesystem path of the SQLite file. ``:memory:`` is supported and
        used heavily by the test-suite.
    read_only:
        Open in read-only mode; the schema is not touched.
    """
    if db_path == ":memory:":
        # check_same_thread=False: the API server calls into the connection
        # from worker threads; SQLite's own locking keeps access safe.
        conn = sqlite3.connect(":memory:", check_same_thread=False)
    else:
        path = Path(db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if read_only:
            uri = f"file:{path.as_posix()}?mode=ro"
            conn = sqlite3.connect(uri, uri=True)
        else:
            conn = sqlite3.connect(str(path), check_same_thread=False)

    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=5000")
    if not read_only:
        apply_schema(conn)
    return conn
