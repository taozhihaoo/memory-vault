"""SQLite connection management.

The whole engine runs on a single SQLite database file. Connections use WAL
journaling so the API server and the file watcher can share the database
without blocking each other.

A single :class:`sqlite3.Connection` is shared by every FastAPI worker
thread. SQLite cursors are *connection-scoped*, not cursor-scoped in practice:
two threads calling ``execute`` on the same connection can consume each
other's result set, which used to make ``/api/health`` randomly return 500
(``TypeError: 'NoneType' object is not subscriptable``) whenever the
dashboard fired its parallel requests. :class:`LockedConnection` serializes
every statement and materialises the rows while the lock is held.
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

from memoryvault.database.schema import apply_schema


class _Result:
    """A materialised, cursor-shaped result that is safe to read later."""

    def __init__(self, cursor: sqlite3.Cursor) -> None:
        self._rows = cursor.fetchall()
        self._index = 0
        self.lastrowid = cursor.lastrowid
        self.rowcount = cursor.rowcount
        self.description = cursor.description

    def fetchone(self):
        if self._index >= len(self._rows):
            return None
        row = self._rows[self._index]
        self._index += 1
        return row

    def fetchall(self):
        remaining = self._rows[self._index:]
        self._index = len(self._rows)
        return remaining

    def fetchmany(self, size: int = 1):
        start = self._index
        self._index = min(len(self._rows), start + size)
        return self._rows[start:self._index]

    def __iter__(self):
        return iter(self._rows)

    def __next__(self):
        row = self.fetchone()
        if row is None:
            raise StopIteration
        return row


class LockedConnection:
    """Thread-safe, eagerly-fetched facade over a ``sqlite3.Connection``."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        object.__setattr__(self, "_conn", conn)
        object.__setattr__(self, "_lock", threading.RLock())

    def execute(self, sql, parameters=()):
        with self._lock:
            cursor = self._conn.execute(sql, parameters)
            return _Result(cursor)

    def executemany(self, sql, parameters):
        with self._lock:
            cursor = self._conn.executemany(sql, parameters)
            return _Result(cursor)

    def executescript(self, script):
        with self._lock:
            return self._conn.executescript(script)

    def commit(self):
        with self._lock:
            return self._conn.commit()

    def rollback(self):
        with self._lock:
            return self._conn.rollback()

    def close(self):
        with self._lock:
            return self._conn.close()

    @property
    def row_factory(self):
        return self._conn.row_factory

    @row_factory.setter
    def row_factory(self, value):
        with self._lock:
            self._conn.row_factory = value

    def __getattr__(self, name):
        return getattr(self._conn, name)

    def __setattr__(self, name, value):
        if name in ("_conn", "_lock"):
            object.__setattr__(self, name, value)
        else:
            setattr(self._conn, name, value)


def connect(db_path: str | Path, *, read_only: bool = False) -> LockedConnection:
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
        # from worker threads; LockedConnection keeps those calls safe.
        raw = sqlite3.connect(":memory:", check_same_thread=False)
    else:
        path = Path(db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if read_only:
            uri = f"file:{path.as_posix()}?mode=ro"
            raw = sqlite3.connect(uri, uri=True)
        else:
            raw = sqlite3.connect(str(path), check_same_thread=False)

    raw.row_factory = sqlite3.Row
    raw.execute("PRAGMA journal_mode=WAL")
    raw.execute("PRAGMA foreign_keys=ON")
    raw.execute("PRAGMA synchronous=NORMAL")
    raw.execute("PRAGMA busy_timeout=5000")
    if not read_only:
        apply_schema(raw)
    return LockedConnection(raw)
