"""Provider abstractions for optional AI extensions.

Contract
--------
* :class:`EmbeddingProvider` — turn text into fixed-size vectors.
* :class:`SummaryProvider`   — condense a document into a short summary.

Implementations are supplied by *applications* that embed MemoryVault (for
example a local ONNX model runner). MemoryVault itself never calls external
services: the only shipped implementations are deterministic and local.
"""

from __future__ import annotations

import hashlib
import math
import re
from abc import ABC, abstractmethod
from typing import Callable, Sequence


class ProviderError(Exception):
    """Base class for provider failures."""


class ProviderNotConfigured(ProviderError):
    """Raised when no provider has been registered for a capability."""


class EmbeddingProvider(ABC):
    """Turns texts into fixed-length vectors."""

    #: Human-readable provider name used for registry lookups.
    name: str = "abstract"

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Vector length produced by :meth:`embed`."""

    @abstractmethod
    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Embed *texts*; returns one vector per input, same order."""

    def embed_one(self, text: str) -> list[float]:
        return self.embed([text])[0]


class SummaryProvider(ABC):
    """Condenses documents into short summaries."""

    name: str = "abstract"

    @abstractmethod
    def summarize(self, text: str, *, max_length: int = 256) -> str:
        """Return a summary of *text* no longer than ~max_length chars."""


class HashingEmbeddingProvider(EmbeddingProvider):
    """Deterministic, fully local reference embedding (feature hashing).

    This is *not* a semantic model — it exists so the extension surface and
    dependent code can be exercised offline in tests. Swap in a real local
    model provider for semantic search.
    """

    name = "hashing"

    def __init__(self, dimension: int = 256) -> None:
        if dimension < 16:
            raise ValueError("dimension must be >= 16")
        self._dimension = dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        vector = [0.0] * self._dimension
        tokens = re.findall(r"\b\w+\b", text.lower())
        for token in tokens:
            digest = hashlib.md5(token.encode("utf-8")).digest()
            slot = int.from_bytes(digest[:4], "big") % self._dimension
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[slot] += sign
        norm = math.sqrt(sum(v * v for v in vector)) or 1.0
        return [v / norm for v in vector]


class NullSummaryProvider(SummaryProvider):
    """Deterministic extractive fallback: first sentences up to max_length."""

    name = "null"

    def summarize(self, text: str, *, max_length: int = 256) -> str:
        text = " ".join(text.split())
        if len(text) <= max_length:
            return text
        cut = text[:max_length]
        for sep in (". ", "! ", "? ", "\n"):
            idx = cut.rfind(sep)
            if idx > max_length // 2:
                return cut[: idx + 1].strip()
        return cut.rstrip() + "…"


class Registry:
    """Tiny name→provider registry so plugins can be swapped at runtime."""

    def __init__(self) -> None:
        self._embedders: dict[str, EmbeddingProvider] = {}
        self._summarizers: dict[str, SummaryProvider] = {}
        self._default_embedder: str | None = None
        self._default_summarizer: str | None = None

    def register_embedding(
        self, provider: EmbeddingProvider, *, default: bool = False
    ) -> None:
        self._embedders[provider.name] = provider
        if default or self._default_embedder is None:
            self._default_embedder = provider.name

    def register_summary(
        self, provider: SummaryProvider, *, default: bool = False
    ) -> None:
        self._summarizers[provider.name] = provider
        if default or self._default_summarizer is None:
            self._default_summarizer = provider.name

    def embedding(self, name: str | None = None) -> EmbeddingProvider:
        key = name or self._default_embedder
        if key is None or key not in self._embedders:
            raise ProviderNotConfigured("no embedding provider registered")
        return self._embedders[key]

    def summary(self, name: str | None = None) -> SummaryProvider:
        key = name or self._default_summarizer
        if key is None or key not in self._summarizers:
            raise ProviderNotConfigured("no summary provider registered")
        return self._summarizers[key]

    @property
    def names(self) -> dict[str, list[str]]:
        return {
            "embedding": sorted(self._embedders),
            "summary": sorted(self._summarizers),
        }


def register_provider_factory(registry: Registry, kind: str, name: str, factory: Callable):
    """Hook for external packages: lazily build a provider on first use."""
    if kind == "embedding":
        registry.register_embedding(factory(), default=False)
    elif kind == "summary":
        registry.register_summary(factory(), default=False)
    else:
        raise ValueError(f"unknown provider kind '{kind}'")
