"""SQLAlchemy declarative base for ORM-mapped tables.

Domain models in shared/models/ never import from here — this module is
persistence-only. Keeping the two separate is what makes SQLite (and this
ORM layer) replaceable later without touching business logic.
"""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Shared declarative base for all ORM table definitions."""
