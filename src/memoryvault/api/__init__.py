"""FastAPI application exposing the vault over HTTP."""

from memoryvault.api.app import create_app

__all__ = ["create_app"]
