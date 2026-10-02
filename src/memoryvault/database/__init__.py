"""SQLite persistence layer."""

from memoryvault.database.connection import connect
from memoryvault.database.repository import DocumentRepository

__all__ = ["connect", "DocumentRepository"]
