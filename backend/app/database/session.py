"""Database engine/session factory.

All SQLite-specific setup (the engine URL, connect args, pragma tuning)
lives here and only here — nothing outside this module knows the
database is SQLite, so swapping engines later is a local change.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from backend.app.config import Settings, get_settings


def create_engine(settings: Settings) -> AsyncEngine:
    """Create the SQLAlchemy async engine for the given settings.

    In-memory SQLite URLs get a StaticPool so the same in-memory database
    is shared across connections within a process (needed for tests).
    """
    connect_args: dict[str, object] = {}
    kwargs: dict[str, object] = {}
    if ":memory:" in settings.database_url:
        connect_args["check_same_thread"] = False
        kwargs["poolclass"] = StaticPool
    return create_async_engine(settings.database_url, connect_args=connect_args, **kwargs)


@lru_cache
def get_engine() -> AsyncEngine:
    """Process-wide engine, built from the current settings."""
    return create_engine(get_settings())


def get_sessionmaker(engine: AsyncEngine | None = None) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine or get_engine(), expire_on_commit=False)


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency yielding a database session."""
    session_factory = get_sessionmaker()
    async with session_factory() as session:
        yield session


async def check_database_connection(engine: AsyncEngine | None = None) -> bool:
    """Readiness check: can we open a connection and run a trivial query?"""
    from sqlalchemy import text

    target_engine = engine or get_engine()
    try:
        async with target_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
