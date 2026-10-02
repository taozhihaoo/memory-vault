"""SimHash: 64-bit locality-sensitive fingerprints for near-duplicate detection.

The implementation is fully deterministic: tokens are hashed with FNV-1a so
fingerprints are stable across processes and platforms.
"""

from __future__ import annotations

import re

_WORD_RE = re.compile(r"\b[\w']+\b", re.UNICODE)

_FNV_OFFSET = 0xCBF29CE484222325
_FNV_PRIME = 0x100000001B3
_MASK_64 = (1 << 64) - 1


def _fnv1a_64(token: str) -> int:
    """Deterministic 64-bit FNV-1a hash of *token*."""
    h = _FNV_OFFSET
    for byte in token.encode("utf-8"):
        h ^= byte
        h = (h * _FNV_PRIME) & _MASK_64
    return h


def hamming_distance(a: int, b: int) -> int:
    """Number of differing bits between two fingerprints."""
    return bin(a ^ b).count("1")


def tokenize(text: str) -> list[str]:
    return [t.lower() for t in _WORD_RE.findall(text)]


class SimHash:
    """Compute and compare 64-bit SimHash fingerprints."""

    def __init__(self, bits: int = 64) -> None:
        if bits not in (32, 64):
            raise ValueError("SimHash supports 32 or 64 bits")
        self.bits = bits

    def fingerprint(self, text: str) -> int:
        """Weighted SimHash of *text* (token frequency = weight)."""
        counts: dict[str, int] = {}
        for token in tokenize(text):
            counts[token] = counts.get(token, 0) + 1
        return self.fingerprint_counts(counts)

    def fingerprint_counts(self, counts: dict[str, int]) -> int:
        vector = [0] * self.bits
        for token, weight in counts.items():
            h = _fnv1a_64(token)
            for i in range(self.bits):
                bit = (h >> i) & 1
                vector[i] += weight if bit else -weight
        fingerprint = 0
        for i, v in enumerate(vector):
            if v > 0:
                fingerprint |= 1 << i
        return fingerprint

    @staticmethod
    def to_hex(fingerprint: int) -> str:
        return f"{fingerprint:016x}"

    @staticmethod
    def from_hex(value: str) -> int:
        return int(value, 16)

    def bands(self, fingerprint: int, bands: int = 4) -> list[int]:
        """Split a fingerprint into *bands* chunks for candidate lookup."""
        width = self.bits // bands
        return [
            (fingerprint >> (i * width)) & ((1 << width) - 1) for i in range(bands)
        ]

    def similarity(self, a: int, b: int) -> float:
        """Jaccard-style bit similarity in [0.0, 1.0]."""
        same = self.bits - hamming_distance(a, b)
        return same / self.bits
