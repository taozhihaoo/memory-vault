"""Near-duplicate detection over the document store."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from memoryvault.config import VaultConfig
from memoryvault.database.repository import DocumentRepository
from memoryvault.dedup.simhash import SimHash, hamming_distance


@dataclass(slots=True)
class DuplicateGroup:
    """A group of documents sharing identical or near-identical content."""

    kind: str  # "exact" | "similar"
    primary_id: int
    document_ids: list[int]
    similarity: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "primary_id": self.primary_id,
            "document_ids": self.document_ids,
            "similarity": self.similarity,
        }


class DuplicateDetector:
    """Finds exact (SHA-256) and near (SimHash) duplicate document groups."""

    def __init__(
        self,
        repo: DocumentRepository,
        *,
        threshold: int | None = None,
        simhash_bits: int = 64,
    ) -> None:
        self.repo = repo
        self.threshold = threshold if threshold is not None else 12
        self.simhash = SimHash(bits=simhash_bits)

    def find_exact_duplicates(self) -> list[DuplicateGroup]:
        by_hash = self.repo.all_sha256()
        return [
            DuplicateGroup(kind="exact", primary_id=ids[0], document_ids=sorted(ids))
            for ids in by_hash.values()
            if len(ids) > 1
        ]

    def find_similar_pairs(self) -> list[DuplicateGroup]:
        fingerprints = self.repo.all_simhashes()
        pairs: dict[tuple[int, int], int] = {}
        ids = sorted(fingerprints)
        for i, doc_a in enumerate(ids):
            fp_a = fingerprints[doc_a]
            for doc_b in ids[i + 1:]:
                fp_b = fingerprints[doc_b]
                if abs(fp_a.bit_count() - fp_b.bit_count()) > self.threshold:
                    continue  # cheap lower-bound on the distance
                distance = hamming_distance(fp_a, fp_b)
                if distance <= self.threshold:
                    pairs[(doc_a, doc_b)] = distance
        return [
            DuplicateGroup(
                kind="similar",
                primary_id=a,
                document_ids=[a, b],
                similarity=round(1 - distance / self.simhash.bits, 4),
            )
            for (a, b), distance in sorted(pairs.items())
        ]

    def similar_to(self, document_id: int, *, limit: int = 10) -> list[dict[str, Any]]:
        """Documents similar to *document_id*, band-indexed candidates first."""
        doc = self.repo.get(document_id)
        if doc is None or doc.simhash is None:
            return []
        fp = int(doc.simhash, 16)
        candidates = self.repo.band_candidates(fp, exclude={document_id})
        others = self.repo.all_simhashes()
        candidates &= set(others)

        scored = []
        for other_id in candidates:
            distance = hamming_distance(fp, others[other_id])
            if distance <= self.threshold * 2:
                scored.append(
                    {
                        "document_id": other_id,
                        "distance": distance,
                        "similarity": round(1 - distance / self.simhash.bits, 4),
                    }
                )
        scored.sort(key=lambda item: item["distance"])
        return scored[:limit]

    def find_all(self) -> dict[str, list[DuplicateGroup]]:
        return {
            "exact": self.find_exact_duplicates(),
            "similar": self.find_similar_pairs(),
        }
