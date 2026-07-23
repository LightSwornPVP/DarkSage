"""Configuration validation tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.app.config import Environment, Settings


def test_default_settings_are_valid() -> None:
    settings = Settings()
    assert settings.environment == Environment.DEVELOPMENT
    assert settings.database_url.startswith("sqlite+aiosqlite://")
    assert 0 < settings.port <= 65535


def test_rejects_unsupported_database_scheme() -> None:
    with pytest.raises(ValidationError):
        Settings(database_url="postgresql://localhost/db")


def test_accepts_valid_relative_async_sqlite_url() -> None:
    settings = Settings(database_url="sqlite+aiosqlite:///./darksage_valid.db")
    assert settings.database_url.startswith("sqlite+aiosqlite://")


def test_accepts_valid_absolute_async_sqlite_url() -> None:
    settings = Settings(database_url="sqlite+aiosqlite:////tmp/darksage_valid.db")
    assert settings.database_url.startswith("sqlite+aiosqlite://")


def test_accepts_valid_in_memory_async_sqlite_url() -> None:
    settings = Settings(database_url="sqlite+aiosqlite:///:memory:")
    assert settings.database_url.startswith("sqlite+aiosqlite://")


def test_rejects_synchronous_sqlite_scheme() -> None:
    """create_async_engine() requires an async driver; bare sqlite:// is sync-only."""
    with pytest.raises(ValidationError):
        Settings(database_url="sqlite:///./darksage.db")


def test_rejects_host_bearing_sqlite_url() -> None:
    """sqlite+aiosqlite://host/database is structurally invalid for a file-based DB."""
    with pytest.raises(ValidationError):
        Settings(database_url="sqlite+aiosqlite://host/database")


def test_rejects_authority_bearing_sqlite_url() -> None:
    with pytest.raises(ValidationError):
        Settings(database_url="sqlite+aiosqlite://user:pass@host:1234/database")


def test_rejects_malformed_database_url() -> None:
    with pytest.raises(ValidationError):
        Settings(database_url="not-a-url-at-all")


def test_rejects_invalid_port() -> None:
    with pytest.raises(ValidationError):
        Settings(port=70000)


def test_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        Settings(some_unexpected_field="value")  # type: ignore[call-arg]


def test_database_path_is_none_for_in_memory_url() -> None:
    settings = Settings(database_url="sqlite+aiosqlite:///:memory:")
    assert settings.database_path is None


def test_database_path_resolves_for_file_url() -> None:
    settings = Settings(database_url="sqlite+aiosqlite:///./darksage_test.db")
    assert settings.database_path is not None
    assert str(settings.database_path).endswith("darksage_test.db")
