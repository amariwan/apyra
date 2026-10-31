"""Async SQLAlchemy session management."""

from __future__ import annotations

import contextlib
import functools
from asyncio import AbstractEventLoop, get_running_loop
from collections.abc import AsyncGenerator, Awaitable
from typing import cast

from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from .base import Base
from .connection import build_async_database_url
from .settings import get_db_settings


class DatabaseSessionManager:
    """Manage a single async SQLAlchemy engine and session factory."""

    def __init__(self, host: str, engine_kwargs: dict[str, object] | None = None) -> None:
        self._host = host
        self._engine_kwargs = dict(engine_kwargs or {})
        engine, sessionmaker = self._new_engine()
        self._engine: AsyncEngine | None = engine
        self._sessionmaker: async_sessionmaker[AsyncSession] | None = sessionmaker
        self._bound_loop: AbstractEventLoop | None = None

    async def close(self) -> None:
        """Dispose the engine; later use creates a fresh engine lazily."""
        if self._engine is not None:
            await self._engine.dispose()
            self._engine = None
            self._sessionmaker = None
            self._bound_loop = None

    @property
    def engine(self) -> AsyncEngine | None:
        return self._engine

    @contextlib.asynccontextmanager
    async def connect(self) -> AsyncGenerator[AsyncConnection]:
        """Yield a transactional connection, rolling back if its body fails."""
        await self._ensure_current_loop()
        if self._engine is None:
            raise RuntimeError("database session manager is not initialized")
        async with self._engine.begin() as connection:
            try:
                yield connection
            except Exception:
                await connection.rollback()
                raise

    @contextlib.asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession]:
        """Yield a session, rolling back on failure and always closing it."""
        await self._ensure_current_loop()
        if self._sessionmaker is None:
            raise RuntimeError("database session manager is not initialized")
        session = self._sessionmaker()
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

    async def _ensure_current_loop(self) -> None:
        current_loop = get_running_loop()
        if self._bound_loop is current_loop:
            return
        if self._engine is None:
            self._engine, self._sessionmaker = self._new_engine()
        elif self._bound_loop is not None:
            await self._engine.dispose()
            self._engine, self._sessionmaker = self._new_engine()
        self._bound_loop = current_loop

    def _new_engine(
        self,
    ) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
        engine = create_async_engine(self._host, **self._engine_kwargs)
        sessionmaker = async_sessionmaker(
            autocommit=False,
            bind=engine,
            expire_on_commit=False,
        )
        return engine, sessionmaker


@functools.cache
def get_sessionmanager() -> DatabaseSessionManager:
    settings = get_db_settings()
    connection_string = build_async_database_url(settings)
    engine_kwargs: dict[str, object] = {
        "echo": _db_setting(settings, "db_engine_echo"),
        "pool_pre_ping": _db_setting(settings, "db_pool_pre_ping"),
    }
    if _db_setting(settings, "db_backend") != "sqlite":
        engine_kwargs.update(
            pool_size=_db_setting(settings, "db_pool_size"),
            max_overflow=_db_setting(settings, "db_max_overflow"),
            pool_recycle=_db_setting(settings, "db_pool_recycle"),
        )
    return DatabaseSessionManager(connection_string, engine_kwargs=engine_kwargs)


async def get_db_session() -> AsyncGenerator[AsyncSession]:
    """Yield a managed async session for dependency injection."""
    async with get_sessionmanager().session() as session:
        yield session


def _db_setting(settings: object, name: str) -> object:
    if hasattr(settings, name):
        return getattr(settings, name)
    return getattr(settings, name.upper(), None)


async def ensure_db_schema() -> None:
    """Create mapped tables when database auto-creation is enabled."""
    settings = get_db_settings()
    enabled = _db_setting(settings, "enabled")
    if enabled is None:
        enabled = _db_setting(settings, "db_enabled")
    auto_create = _db_setting(settings, "db_auto_create_tables")
    if not enabled or not auto_create:
        return
    session_manager = get_sessionmanager()
    ensure_current_loop = getattr(session_manager, "_ensure_current_loop", None)
    if callable(ensure_current_loop):
        await cast(Awaitable[None], ensure_current_loop())
    engine = session_manager.engine
    if engine is None:
        raise RuntimeError("database engine is not initialized")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


DatabaseManager = DatabaseSessionManager
