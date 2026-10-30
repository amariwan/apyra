import pytest
from sqlalchemy import text

from apyra.db import DatabaseManager, DbSettings, build_async_database_url


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


def test_disabled_database_raises() -> None:
    settings = DbSettings(db_enabled=False)
    with pytest.raises(RuntimeError):
        build_async_database_url(settings)
