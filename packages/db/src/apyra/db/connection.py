"""Database URL builders."""

from __future__ import annotations

from typing import Any

from sqlalchemy import URL

from .settings import DbSettings, get_db_settings


def _setting(settings: DbSettings, name: str) -> Any:
    if hasattr(settings, name):
        return getattr(settings, name)
    return getattr(settings, name.upper())


_DEFAULT_PORTS = {"postgresql": 5432, "mysql": 3306}


def _build_database_url(*, asynchronous: bool, db_settings: DbSettings | None = None) -> str:
    settings = db_settings or get_db_settings()
    if not settings.enabled:
        raise RuntimeError("database is disabled")

    if _setting(settings, "db_backend") == "sqlite":
        driver = "sqlite+aiosqlite" if asynchronous else "sqlite+pysqlite"
        return URL.create(driver, database=_setting(settings, "db_database")).render_as_string(
            hide_password=False
        )

    driver = {
        ("postgresql", True): "postgresql+asyncpg",
        ("postgresql", False): "postgresql+psycopg",
        ("mysql", True): "mysql+asyncmy",
        ("mysql", False): "mysql+pymysql",
    }[(_setting(settings, "db_backend"), asynchronous)]
    return URL.create(
        driver,
        username=_setting(settings, "db_username"),
        password=_setting(settings, "db_password"),
        host=_setting(settings, "db_ip"),
        port=_setting(settings, "db_port") or _DEFAULT_PORTS[_setting(settings, "db_backend")],
        database=_setting(settings, "db_database"),
    ).render_as_string(hide_password=False)


def build_async_database_url(db_settings: DbSettings | None = None) -> str:
    return _build_database_url(asynchronous=True, db_settings=db_settings)


def build_sync_database_url(db_settings: DbSettings | None = None) -> str:
    return _build_database_url(asynchronous=False, db_settings=db_settings)
