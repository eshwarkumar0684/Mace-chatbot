"""ASGI entrypoint for platforms that run `uvicorn app:app` from the repository root."""

from backend.app import app

__all__ = ["app"]
