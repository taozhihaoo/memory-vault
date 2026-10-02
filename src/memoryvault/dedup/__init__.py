"""Duplicate detection: exact SHA-256 matches plus SimHash near-duplicates."""

from memoryvault.dedup.simhash import SimHash, hamming_distance
from memoryvault.dedup.detector import DuplicateDetector

__all__ = ["SimHash", "hamming_distance", "DuplicateDetector"]
