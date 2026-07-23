"""Application startup tests."""

from __future__ import annotations

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient
from pydantic import ValidationError


def test_create_app_returns_fastapi_instance(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DARKSAGE_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    from backend.app.main import create_app

    app = create_app()
    assert isinstance(app, FastAPI)
    assert app.title == "DarkSage API"


def test_create_app_registers_health_routes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prove /health and /ready are wired up by actually calling them.

    Inspecting `app.routes` directly is brittle: FastAPI's router can hold
    internal wrapper nodes (e.g. for included routers) that never expose a
    `.path` attribute, so route registration is verified functionally
    instead of by walking route internals.
    """
    monkeypatch.setenv("DARKSAGE_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    from backend.app.main import create_app

    app = create_app()
    with TestClient(app) as test_client:
        health_response = test_client.get("/health")
        ready_response = test_client.get("/ready")

    assert health_response.status_code == status.HTTP_200_OK
    assert health_response.json() == {"status": "ok"}
    assert ready_response.status_code == status.HTTP_200_OK
    assert ready_response.json() == {"status": "ready", "database": "ok"}


def test_app_fails_clearly_on_invalid_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """Startup must fail loudly, not silently, on invalid configuration."""
    monkeypatch.setenv("DARKSAGE_DATABASE_URL", "postgresql://not-supported-in-this-slice")
    from backend.app.config import get_settings

    with pytest.raises(ValidationError):
        get_settings()
