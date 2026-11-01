"""Database wiring for the reference application."""

from __future__ import annotations

import os

from apyra.db import DatabaseManager, DbSettings, build_async_database_url


def _database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if url:
        return url
    backend = os.getenv("DB_BACKEND", "sqlite")
    if backend == "postgres":
        host = os.getenv("DB_HOST", "localhost")
        port = os.getenv("DB_PORT", "5432")
        user = os.getenv("DB_USER", "apyra")
        password = os.getenv("DB_PASSWORD", "apyra")
        database = os.getenv("DB_NAME", "apyra_reference")
        return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{database}"
    return "sqlite+aiosqlite:///./reference.db"


def create_session_manager() -> DatabaseManager:
    url = _database_url()
    if url.startswith("sqlite") and ":memory:" in url:
        settings = DbSettings(db_enabled=True, db_backend="sqlite", db_database=":memory:")
        url = build_async_database_url(settings).replace(":memory:", ":memory:?cache=shared")
    return DatabaseManager(url)
