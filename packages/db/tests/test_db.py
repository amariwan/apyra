import asyncio
import gc
import warnings
from typing import Literal

import pytest
from sqlalchemy import String, text
from sqlalchemy.orm import Mapped, mapped_column

from apyra.db import (
    Base,
    DatabaseManager,
    DbSettings,
    build_async_database_url,
    build_sync_database_url,
)
from apyra.db import session as session_module


class SchemaProbe(Base):
    __tablename__ = "schema_probe"

    id: Mapped[str] = mapped_column(String, primary_key=True)


@pytest.mark.asyncio
async def test_sqlite_session_executes_query() -> None:
    settings = DbSettings(db_enabled=True, db_backend="sqlite", db_database=":memory:")
    url = build_async_database_url(settings)
    manager = DatabaseManager(url, engine_kwargs={"echo": False})
    try:
        async with manager.session() as session:
            result = await session.execute(text("select 1"))
            assert result.scalar_one() == 1
    finally:
        await manager.close()


@pytest.mark.asyncio
async def test_session_manager_can_be_reused_after_close() -> None:
    settings = DbSettings(db_enabled=True, db_backend="sqlite", db_database=":memory:")
    manager = DatabaseManager(build_async_database_url(settings), engine_kwargs={"echo": False})
    try:
        async with manager.session() as session:
            result = await session.execute(text("select 1"))
            assert result.scalar_one() == 1

        await manager.close()

        async with manager.session() as session:
            result = await session.execute(text("select 1"))
            assert result.scalar_one() == 1
    finally:
        await manager.close()


@pytest.mark.asyncio
async def test_connect_rolls_back_when_context_body_fails() -> None:
    settings = DbSettings(db_enabled=True, db_backend="sqlite", db_database=":memory:")
    manager = DatabaseManager(build_async_database_url(settings), engine_kwargs={"echo": False})
    try:
        async with manager.connect() as connection:
            await connection.execute(text("create table records (value integer)"))

        with pytest.raises(RuntimeError, match="abort transaction"):
            async with manager.connect() as connection:
                await connection.execute(text("insert into records values (1)"))
                raise RuntimeError("abort transaction")

        async with manager.connect() as connection:
            result = await connection.execute(text("select count(*) from records"))
            assert result.scalar_one() == 0
    finally:
        await manager.close()


@pytest.mark.asyncio
async def test_session_rolls_back_when_context_body_fails() -> None:
    settings = DbSettings(db_enabled=True, db_backend="sqlite", db_database=":memory:")
    manager = DatabaseManager(build_async_database_url(settings), engine_kwargs={"echo": False})
    try:
        async with manager.connect() as connection:
            await connection.execute(text("create table records (value integer)"))

        with pytest.raises(RuntimeError, match="abort transaction"):
            async with manager.session() as session:
                await session.execute(text("insert into records values (1)"))
                raise RuntimeError("abort transaction")

        async with manager.session() as session:
            result = await session.execute(text("select count(*) from records"))
            assert result.scalar_one() == 0
    finally:
        await manager.close()


def test_session_manager_rebinds_between_event_loops_without_leaking() -> None:
    settings = DbSettings(db_enabled=True, db_backend="sqlite", db_database=":memory:")
    manager = DatabaseManager(build_async_database_url(settings), engine_kwargs={"echo": False})

    async def query() -> None:
        async with manager.session() as session:
            result = await session.execute(text("select 1"))
            assert result.scalar_one() == 1

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", ResourceWarning)
        try:
            asyncio.run(query())
            asyncio.run(query())
        finally:
            asyncio.run(manager.close())
            gc.collect()

    connection_warnings = [
        warning
        for warning in caught
        if issubclass(warning.category, ResourceWarning)
        and "was deleted before being closed" in str(warning.message)
    ]
    assert connection_warnings == []


def test_disabled_database_raises() -> None:
    settings = DbSettings(db_enabled=False)
    with pytest.raises(RuntimeError):
        build_async_database_url(settings)


@pytest.mark.parametrize(
    ("backend", "port", "async_driver", "sync_driver", "default_port"),
    [
        ("postgresql", None, "postgresql+asyncpg", "postgresql+psycopg", 5432),
        ("mysql", None, "mysql+asyncmy", "mysql+pymysql", 3306),
        ("postgresql", 5544, "postgresql+asyncpg", "postgresql+psycopg", 5544),
    ],
)
def test_database_url_builders_select_drivers_and_escape_credentials(
    backend: Literal["postgresql", "mysql"],
    port: int | None,
    async_driver: str,
    sync_driver: str,
    default_port: int,
) -> None:
    settings = DbSettings(
        db_enabled=True,
        db_backend=backend,
        db_username="db-user",
        db_password="p@ss:/word",
        db_database="app-db",
        db_ip="db.example",
        db_port=port,
    )

    assert build_async_database_url(settings) == (
        f"{async_driver}://db-user:p%40ss%3A%2Fword@db.example:{default_port}/app-db"
    )
    assert build_sync_database_url(settings) == (
        f"{sync_driver}://db-user:p%40ss%3A%2Fword@db.example:{default_port}/app-db"
    )


@pytest.mark.parametrize("port", [0, -1, 65536])
def test_database_settings_reject_out_of_range_ports(port: int) -> None:
    with pytest.raises(ValueError):
        DbSettings(
            db_enabled=True,
            db_backend="postgresql",
            db_username="db-user",
            db_password="db-password",
            db_database="app-db",
            db_port=port,
        )


def test_db_settings_repr_redacts_password() -> None:
    settings = DbSettings(
        db_enabled=True,
        db_username="user",
        db_password="db-password-secret",
        db_database="app",
    )

    assert "db-password-secret" not in repr(settings)


@pytest.mark.asyncio
async def test_ensure_db_schema_creates_tables_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = DbSettings(
        db_enabled=True,
        db_backend="sqlite",
        db_database=":memory:",
        db_auto_create_tables=True,
    )
    manager = DatabaseManager(build_async_database_url(settings), engine_kwargs={"echo": False})
    monkeypatch.setattr(session_module, "get_db_settings", lambda: settings)
    monkeypatch.setattr(session_module, "get_sessionmanager", lambda: manager)
    try:
        await session_module.ensure_db_schema()
        async with manager.connect() as connection:
            result = await connection.execute(
                text("select name from sqlite_master where type='table' and name='schema_probe'")
            )
            assert result.scalar_one() == "schema_probe"
    finally:
        await manager.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("db_enabled", "auto_create"),
    [(False, True), (True, False)],
)
async def test_ensure_db_schema_skips_disabled_configuration(
    monkeypatch: pytest.MonkeyPatch, db_enabled: bool, auto_create: bool
) -> None:
    settings = DbSettings(
        db_enabled=db_enabled,
        db_backend="sqlite",
        db_database=":memory:",
        db_auto_create_tables=auto_create,
    )

    def unexpected_manager() -> DatabaseManager:
        raise AssertionError("disabled schema creation must not initialize the database")

    monkeypatch.setattr(session_module, "get_db_settings", lambda: settings)
    monkeypatch.setattr(session_module, "get_sessionmanager", unexpected_manager)

    await session_module.ensure_db_schema()
