"""AI provider abstraction tests (local deterministic implementations only)."""

from __future__ import annotations

import math

import pytest

from memoryvault.ai import (
    EmbeddingProvider,
    HashingEmbeddingProvider,
    NullSummaryProvider,
    ProviderNotConfigured,
    Registry,
    SummaryProvider,
)


# ------------------------------------------------------------- embedding
def test_hashing_embedding_is_deterministic():
    provider = HashingEmbeddingProvider()
    assert provider.embed(["hello world"]) == provider.embed(["hello world"])


def test_hashing_embedding_normalized():
    provider = HashingEmbeddingProvider(dimension=64)
    vector = provider.embed_one("the quick brown fox jumps")
    assert len(vector) == 64
    assert math.isclose(sum(v * v for v in vector), 1.0, rel_tol=1e-6)


def test_hashing_embedding_same_text_same_vector_different_text_differs():
    provider = HashingEmbeddingProvider()
    a = provider.embed_one("alpha beta")
    b = provider.embed_one("alpha beta")
    c = provider.embed_one("totally different words here")
    assert a == b
    assert a != c


def test_embedding_provider_is_abstract():
    with pytest.raises(TypeError):
        EmbeddingProvider()  # type: ignore[abstract]


def test_hashing_embedding_min_dimension():
    with pytest.raises(ValueError):
        HashingEmbeddingProvider(dimension=4)


# --------------------------------------------------------------- summary
def test_null_summary_short_text_passthrough():
    provider = NullSummaryProvider()
    assert provider.summarize("short text") == "short text"


def test_null_summary_truncates_at_sentence():
    provider = NullSummaryProvider()
    text = "First sentence here. " * 30
    summary = provider.summarize(text, max_length=120)
    assert len(summary) <= 120
    assert summary.endswith(".")


def test_summary_provider_is_abstract():
    with pytest.raises(TypeError):
        SummaryProvider()  # type: ignore[abstract]


# -------------------------------------------------------------- registry
def test_registry_starts_empty():
    registry = Registry()
    with pytest.raises(ProviderNotConfigured):
        registry.embedding()
    with pytest.raises(ProviderNotConfigured):
        registry.summary()


def test_registry_roundtrip_and_defaults():
    registry = Registry()
    embedder = HashingEmbeddingProvider()
    summarizer = NullSummaryProvider()
    registry.register_embedding(embedder, default=True)
    registry.register_summary(summarizer)
    assert registry.embedding() is embedder
    assert registry.summary() is summarizer
    assert registry.names == {"embedding": ["hashing"], "summary": ["null"]}


def test_registry_named_lookup():
    registry = Registry()
    registry.register_embedding(HashingEmbeddingProvider(), default=True)
    assert registry.embedding("hashing").dimension == 256
    with pytest.raises(ProviderNotConfigured):
        registry.embedding("missing")
