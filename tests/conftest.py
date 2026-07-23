"""Shared pytest fixtures.

Every fixture here uses an isolated in-memory SQLite database — no test
ever touches a real dev database file or requires network/API keys.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncEngine

from backend.app.config import Settings
from backend.app.database.base import Base
from backend.app.database.session import create_engine, get_engine


@pytest.fixture(autouse=True)
def _reset_engine_cache() -> Iterator[None]:
    """Prevent the process-wide cached engine from leaking between tests."""
    get_engine.cache_clear()
    yield
    get_engine.cache_clear()


@pytest.fixture
def test_settings() -> Settings:
    return Settings(database_url="sqlite+aiosqlite:///:memory:", environment="testing")


@pytest.fixture
async def test_engine(test_settings: Settings) -> AsyncIterator[AsyncEngine]:
    engine = create_engine(test_settings)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("DARKSAGE_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("DARKSAGE_ENVIRONMENT", "testing")
    from backend.app.main import create_app

    app = create_app()
    with TestClient(app) as test_client:
        yield test_client
