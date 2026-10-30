import uuid

import pytest
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from apyra.db import Base, DatabaseManager, DbSettings, Repository, build_async_database_url


class Item(Base):
    __tablename__ = "items"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String, nullable=False)


@pytest.mark.asyncio
async def test_repository_crud() -> None:
    settings = DbSettings(db_enabled=True, db_backend="sqlite", db_database=":memory:")
    manager = DatabaseManager(build_async_database_url(settings), engine_kwargs={"echo": False})
    try:
        await manager._ensure_current_loop()
        engine = manager.engine
        assert engine is not None
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with manager.session() as session:
            repo = Repository(session, Item)
            item = await repo.create(name="first")
            assert item.name == "first"
            fetched = await repo.get(item.id)
            assert fetched is not None
            assert fetched.name == "first"
            items = await repo.list()
            assert len(items) == 1
            await repo.update(item, name="updated")
            assert item.name == "updated"
            await repo.delete(item)
            assert await repo.get(item.id) is None
    finally:
        await manager.close()


@pytest.mark.asyncio
async def test_repository_filtering_sorting_and_cursor_pagination() -> None:
    settings = DbSettings(db_enabled=True, db_backend="sqlite", db_database=":memory:")
    manager = DatabaseManager(build_async_database_url(settings), engine_kwargs={"echo": False})
    try:
        await manager._ensure_current_loop()
        engine = manager.engine
        assert engine is not None
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with manager.session() as session:
            repo = Repository(session, Item)
            await repo.create(name="b")
            await repo.create(name="a")
            await repo.create(name="a")

            filtered = await repo.list(filters={"name": "a"}, order_by="name")
            assert len(filtered) == 2

            page = await repo.page(filters={"name": "a"}, limit=1, offset=0)
            assert page.total == 2
            assert len(page.items) == 1

            first = await repo.paginate(limit=1, order_by="name")
            assert len(first.items) == 1
            assert first.has_more is True
            assert first.next_cursor is not None

            second = await repo.paginate(cursor=first.next_cursor, limit=1, order_by="name")
            assert len(second.items) == 1
            assert second.has_more is False
    finally:
        await manager.close()
