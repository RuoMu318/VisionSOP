"""ASGI entrypoint used by Uvicorn and Docker."""

from .app import create_app

app = create_app()
