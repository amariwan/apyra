"""Async database infrastructure for Apyra."""

from __future__ import annotations

from .base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from .connection import build_async_database_url, build_sync_database_url
from .repository import CursorPage, Page, Repository
from .session import (
    DatabaseManager,
    DatabaseSessionManager,
    ensure_db_schema,
    get_db_session,
    get_sessionmanager,
)
from .settings import DatabaseSettings, DbSettings, get_db_settings

__all__ = [
    "Base",
    "CursorPage",
    "DatabaseManager",
    "DatabaseSessionManager",
    "DatabaseSettings",
    "DbSettings",
    "Page",
    "Repository",
    "TimestampMixin",
    "UUIDPrimaryKeyMixin",
    "build_async_database_url",
    "build_sync_database_url",
    "ensure_db_schema",
    "get_db_session",
    "get_db_settings",
    "get_sessionmanager",
]
