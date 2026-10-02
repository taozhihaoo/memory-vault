"""Timeline service: per-document history and vault activity views."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from memoryvault.database.repository import DocumentRepository, utc_now_iso


class TimelineService:
    """Read-only views over the append-only ``document_events`` table."""

    def __init__(self, repo: DocumentRepository) -> None:
        self.repo = repo

    def document_history(self, document_id: int) -> list[dict[str, Any]]:
        """Every recorded event for one document, oldest first."""
        events = self.repo.list_events(document_id=document_id, limit=1000)
        return [e.to_dict() for e in reversed(events)]

    def recent(self, *, limit: int = 50, event_type: str | None = None) -> list[dict[str, Any]]:
        events = self.repo.list_events(limit=limit, event_type=event_type)
        return [e.to_dict() for e in events]

    def activity(self, *, days: int = 90, group_by: str = "day") -> dict[str, Any]:
        """Aggregated activity for charts.

        ``group_by='day'`` yields per-day buckets; ``group_by='month'``
        aggregates to ``YYYY-MM``.
        """
        histogram = self.repo.activity_histogram(days=days)
        if group_by == "month":
            merged: dict[str, dict[str, int]] = defaultdict(dict)
            for bucket in histogram:
                month = bucket["date"][:7]
                for event_type, n in bucket["counts"].items():
                    merged[month][event_type] = merged[month].get(event_type, 0) + n
            histogram = [
                {"date": month, "counts": counts, "total": sum(counts.values())}
                for month, counts in sorted(merged.items())
            ]
        totals: dict[str, int] = defaultdict(int)
        for bucket in histogram:
            for event_type, n in bucket["counts"].items():
                totals[event_type] += n
        return {
            "generated_at": utc_now_iso(),
            "group_by": group_by,
            "buckets": histogram,
            "totals": dict(totals),
        }

    def document_counts_by_type(self) -> list[dict[str, Any]]:
        row = self.repo.stats()
        return [
            {"content_type": name, "count": count}
            for name, count in sorted(
                row["content_types"].items(), key=lambda kv: -kv[1]
            )
        ]
