"""Build a reproducible demo vault for documentation screenshots.

Indexes a sample-document folder and adds a deterministic, plausible activity
history so the timeline chart has more than a single bar. This script only
touches the vault file you point it at — it is never run by the application.

Usage::

    python scripts/make_demo_vault.py examples/sample-docs --db /tmp/en.db
    python scripts/make_demo_vault.py examples/sample-docs-zh --db /tmp/zh.db
"""

from __future__ import annotations

import argparse
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

from memoryvault import Vault

SEED = 20261109


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("docs", type=Path, help="Directory of sample documents")
    parser.add_argument("--db", type=Path, required=True, help="Vault file to create")
    parser.add_argument("--days", type=int, default=21, help="Days of activity to synthesise")
    args = parser.parse_args()

    if not args.docs.is_dir():
        parser.error(f"not a directory: {args.docs}")
    if args.db.exists():
        args.db.unlink()
    for suffix in ("-wal", "-shm"):
        sidecar = Path(str(args.db) + suffix)
        if sidecar.exists():
            sidecar.unlink()

    with Vault.open(args.db) as vault:
        stats = vault.index(args.docs)
        documents = vault.repo.list_documents(limit=100)
        rng = random.Random(SEED)
        today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

        for days_ago in range(args.days - 1, -1, -1):
            day = today - timedelta(days=days_ago)
            for index in range(rng.choice([0, 1, 1, 2, 2, 3, 4])):
                doc = rng.choice(documents)
                kind = rng.choices(["indexed", "updated"], weights=[3, 1])[0]
                moment = day.replace(hour=9 + min(index, 8), minute=rng.randint(0, 59))
                vault.repo.add_event(
                    document_id=doc.id,
                    path=doc.path,
                    event_type=kind,
                    title=doc.title,
                    detail="demo activity",
                    occurred_at=moment.strftime("%Y-%m-%dT%H:%M:%SZ"),
                )

        # add_event() is intentionally commit-free (callers batch writes),
        # so commit the synthesised history explicitly before closing.
        vault.conn.commit()
        print(
            f"demo vault: {args.db} — {stats.created} documents, "
            f"{vault.repo.count_events()} events over {args.days} days"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
