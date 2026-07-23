"""SQLite initialization tests."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from backend.app.config import Settings
from backend.app.database.session import check_database_connection, create_engine


async def test_engine_initializes_and_runs_query(test_engine: AsyncEngine) -> None:
    async with test_engine.connect() as conn:
        result = await conn.execute(text("SELECT 1"))
        assert result.scalar_one() == 1


async def test_check_database_connection_true_when_reachable(test_engine: AsyncEngine) -> None:
    assert await check_database_connection(test_engine) is True


async def test_check_database_connection_false_when_unreachable() -> None:
    broken_settings = Settings(database_url="sqlite+aiosqlite:////nonexistent/path/does/not/exist.db")
    broken_engine = create_engine(broken_settings)
    assert await check_database_connection(broken_engine) is False
    await broken_engine.dispose()
