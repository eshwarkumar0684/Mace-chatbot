"""ASGI entrypoint for Railway — run `uvicorn app:app` from the repository root."""

from backend.app import app

__all__ = ["app"]
