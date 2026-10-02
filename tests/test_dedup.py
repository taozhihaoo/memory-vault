"""SimHash and duplicate-detection tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from memoryvault.dedup import DuplicateDetector, SimHash, hamming_distance

BASE = (
    "the quick brown fox jumps over the lazy dog while the sun sets slowly "
    "behind the western hills and the river flows on"
)


def test_simhash_identical_text_identical_fingerprint():
    sh = SimHash()
    assert sh.fingerprint(BASE) == sh.fingerprint(BASE)


def test_simhash_deterministic_across_instances():
    assert SimHash().fingerprint(BASE) == SimHash().fingerprint(BASE)


def test_simhash_small_edit_small_distance():
    sh = SimHash()
    fp_a = sh.fingerprint(BASE)
    edited = BASE.replace("western hills", "western hills and meadows")
    fp_b = sh.fingerprint(edited)
    assert hamming_distance(fp_a, fp_b) <= 12


def test_simhash_different_text_large_distance():
    sh = SimHash()
    other = "completely unrelated words about submarine cables and coral reefs"
    assert hamming_distance(sh.fingerprint(BASE), sh.fingerprint(other)) > 20


def test_simhash_hex_roundtrip():
    sh = SimHash()
    fp = sh.fingerprint(BASE)
    assert SimHash.from_hex(SimHash.to_hex(fp)) == fp
    assert len(SimHash.to_hex(fp)) == 16


def test_simhash_bands_partition_bits():
    sh = SimHash()
    fp = 0x0123456789ABCDEF
    bands = sh.bands(fp, bands=4)
    assert len(bands) == 4
    assert all(0 <= b < (1 << 16) for b in bands)
    assert (bands[3] << 48) | (bands[2] << 32) | (bands[1] << 16) | bands[0] == fp


def test_simhash_similarity_bounds():
    sh = SimHash()
    fp = sh.fingerprint(BASE)
    assert sh.similarity(fp, fp) == 1.0
    assert 0.0 <= sh.similarity(fp, ~fp & ((1 << 64) - 1)) <= 1.0


def test_hamming_distance_basic():
    assert hamming_distance(0, 0) == 0
    assert hamming_distance(0, 1) == 1
    assert hamming_distance(0b1010, 0b0101) == 4


def test_simhash_rejects_bad_width():
    with pytest.raises(ValueError):
        SimHash(bits=17)


# -------------------------------------------------------------- detector
def test_detector_finds_exact_duplicates(indexed_vault):
    groups = indexed_vault.dedup.find_exact_duplicates()
    assert len(groups) == 1
    assert sorted(groups[0].document_ids) == groups[0].document_ids
    paths = {indexed_vault.repo.get(i).path for i in groups[0].document_ids}
    names = {Path(p).name for p in paths}
    assert names == {"beta-notes.md", "beta-copy.md"}


def test_detector_finds_similar_pairs(indexed_vault):
    groups = indexed_vault.dedup.find_similar_pairs()
    # beta + copy are identical -> similarity 1.0
    assert any(g.similarity == 1.0 for g in groups)


def test_detector_similar_to_returns_neighbors(indexed_vault):
    docs = indexed_vault.repo.list_documents(limit=100)
    beta = next(d for d in docs if Path(d.path).name == "beta-notes.md")
    neighbors = indexed_vault.dedup.similar_to(beta.id)
    assert neighbors
    assert neighbors[0]["similarity"] >= 0.9


def test_detector_similar_to_unknown_document(indexed_vault):
    assert indexed_vault.dedup.similar_to(99999) == []


def test_find_all_combines_both_kinds(indexed_vault):
    found = indexed_vault.dedup.find_all()
    assert set(found) == {"exact", "similar"}
    assert found["exact"] and found["similar"]


def test_detector_threshold_configurable():
    from memoryvault.database.connection import connect
    from memoryvault.database.repository import DocumentRepository

    repo = DocumentRepository(connect(":memory:"))
    detector = DuplicateDetector(repo, threshold=1)
    assert detector.threshold == 1
