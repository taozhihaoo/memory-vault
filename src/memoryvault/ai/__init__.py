"""Optional AI extension layer.

MemoryVault's core is deterministic and never performs network calls. This
package defines the plugin contracts (embedding, summarization) so external
providers can be plugged in by applications embedding MemoryVault. The
library ships only local, deterministic reference implementations; no
external AI calls are implemented anywhere.
"""

from memoryvault.ai.providers import (
    EmbeddingProvider,
    HashingEmbeddingProvider,
    NullSummaryProvider,
    ProviderError,
    ProviderNotConfigured,
    Registry,
    SummaryProvider,
)

__all__ = [
    "EmbeddingProvider",
    "SummaryProvider",
    "HashingEmbeddingProvider",
    "NullSummaryProvider",
    "ProviderError",
    "ProviderNotConfigured",
    "Registry",
]
