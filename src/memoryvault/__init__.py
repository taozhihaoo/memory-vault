"""MemoryVault — a local-first personal knowledge management engine.

MemoryVault indexes, organizes, searches and visualizes personal documents
entirely offline. The core (parsing, indexing, search) is deterministic and
requires no AI; AI capabilities are an optional plugin layer
(see :mod:`memoryvault.ai`).
"""

__version__ = "1.0.0"

from memoryvault.config import VaultConfig
from memoryvault.vault import Vault

__all__ = ["VaultConfig", "Vault", "__version__"]
