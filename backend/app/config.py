"""Central configuration/settings for the DarkSage backend.

Reads from environment variables and an optional ``.env`` file
(SECURITY_RULES.md: never commit secrets; use env vars in development).
Ships with safe local defaults so the app starts with zero configuration,
but fails loudly (raises at startup, not silently at first use) on
malformed values — see ARCHITECTURE.md Section 28, "fail closed".

No real API keys, no paid services, and no broker credentials are
defined here in this slice.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError


class Environment(str, Enum):
    DEVELOPMENT = "development"
    TESTING = "testing"
    PAPER = "paper"
    PRODUCTION = "production"


# Async drivernames this slice's `create_async_engine()` can use (as reported
# by SQLAlchemy's `URL.drivername`, i.e. without the "://"). Extend this
# tuple (e.g. with "postgresql+asyncpg") when a future slice adds another
# async backend.
_SUPPORTED_ASYNC_DRIVERNAMES: tuple[str, ...] = ("sqlite+aiosqlite",)


class Settings(BaseSettings):
    """Application settings. Instantiate via :func:`get_settings`."""

    model_config = SettingsConfigDict(
        env_prefix="DARKSAGE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="forbid",
    )

    environment: Environment = Environment.DEVELOPMENT
    debug: bool = True
    host: str = "127.0.0.1"
    port: int = Field(default=8000, gt=0, le=65535)

    # SQLite by default (ARCHITECTURE.md Section 20). Async driver so the
    # same config works with FastAPI's async request handlers.
    database_url: str = "sqlite+aiosqlite:///./darksage.db"

    @field_validator("database_url")
    @classmethod
    def _database_url_must_be_a_valid_async_sqlite_url(cls, value: str) -> str:
        try:
            url = make_url(value)
        except ArgumentError as exc:
            raise ValueError(f"database_url is not a valid database URL: {exc}") from exc

        if url.drivername not in _SUPPORTED_ASYNC_DRIVERNAMES:
            raise ValueError(
                "database_url must use an async driver supported in this slice "
                f"({', '.join(_SUPPORTED_ASYNC_DRIVERNAMES)}); got drivername="
                f"{url.drivername!r} from {value!r}. The synchronous sqlite "
                "drivername is rejected because create_async_engine() requires "
                "an async DBAPI driver. Other backends are a future, "
                "explicitly-approved change (see ARCHITECTURE.md Section 20)."
            )
        if url.host or url.username or url.password or url.port:
            raise ValueError(
                "database_url must not include a host/authority component for "
                f"SQLite (got {value!r}); use sqlite+aiosqlite:///relative/path.db, "
                "sqlite+aiosqlite:////absolute/path.db, or "
                "sqlite+aiosqlite:///:memory:"
            )
        if not url.database:
            raise ValueError(
                f"database_url must include a database file path or ':memory:' "
                f"(got {value!r})"
            )
        return value

    @property
    def database_path(self) -> Path | None:
        """Filesystem path for the SQLite file, or None for in-memory DBs."""
        if ":memory:" in self.database_url:
            return None
        # sqlite(+aiosqlite):///relative/path.db or ...:////absolute/path.db
        _, _, path_part = self.database_url.partition(":///")
        return Path(path_part) if path_part else None


def get_settings() -> Settings:
    """Construct and validate Settings. Raises pydantic.ValidationError on
    invalid configuration — callers should let this propagate at startup
    rather than catching it, so misconfiguration fails clearly and early.
    """
    return Settings()
