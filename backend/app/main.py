"""FastAPI application factory and entry point.

Run locally with: uvicorn backend.app.main:app --reload
"""

from __future__ import annotations

from fastapi import FastAPI

from backend.app.api.health import router as health_router
from backend.app.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="DarkSage API",
        debug=settings.debug,
    )
    app.include_router(health_router)
    return app


app = create_app()
