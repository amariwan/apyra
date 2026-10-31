import base64
import json
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import cast

import pytest
from sqlalchemy import Date, DateTime, LargeBinary, Numeric, String, Uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from apyra.db import Base, DatabaseManager, DbSettings, Repository, build_async_database_url


class Item(Base):
    __tablename__ = "items"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String, nullable=False)
    rank: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    event_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    uuid_value: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    binary_value: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)


@pytest.mark.asyncio
async def test_cursor_pagination_rejects_oversized_cursor_json() -> None:
    payload = json.dumps(["x" * 20_000]).encode("utf-8")
    cursor = base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")
    repository = Repository(cast(AsyncSession, object()), Item)

    with pytest.raises(ValueError, match="cursor is invalid"):
        await repository.paginate(cursor=cursor)


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

            with pytest.raises(ValueError, match="cursor is invalid"):
                await repo.paginate(cursor="%%%", limit=1)
            object_cursor = base64.urlsafe_b64encode(b"{}").decode("ascii").rstrip("=")
            with pytest.raises(ValueError, match="cursor is invalid"):
                await repo.paginate(cursor=object_cursor, limit=1)
            nested_cursor = (
                base64.urlsafe_b64encode(b'[[{"invalid":"value"}]]').decode("ascii").rstrip("=")
            )
            with pytest.raises(ValueError, match="cursor values must be scalar"):
                await repo.paginate(cursor=nested_cursor, limit=1)

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
            assert second.has_more is True
            assert second.next_cursor is not None

            third = await repo.paginate(cursor=second.next_cursor, limit=1, order_by="name")
            assert len(third.items) == 1
            assert third.has_more is False
            assert [item.name for item in first.items + second.items + third.items] == [
                "a",
                "a",
                "b",
            ]
    finally:
        await manager.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("descending", [False, True])
async def test_cursor_pagination_includes_null_sort_values_after_non_null_values(
    descending: bool,
) -> None:
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
            await repo.create(id="a", name="first", rank="a")
            await repo.create(id="b", name="second", rank=None)
            await repo.create(id="c", name="third", rank=None)

            page = await repo.paginate(limit=1, order_by="rank", descending=descending)
            assert page.items[0].id == "a"
            assert page.has_more is True
            assert page.next_cursor is not None

            seen = [page.items[0].id]
            cursor = page.next_cursor
            while cursor is not None:
                page = await repo.paginate(
                    cursor=cursor, limit=1, order_by="rank", descending=descending
                )
                seen.extend(item.id for item in page.items)
                cursor = page.next_cursor

            assert seen == (["a", "c", "b"] if descending else ["a", "b", "c"])
    finally:
        await manager.close()


@pytest.mark.asyncio
async def test_cursor_pagination_preserves_typed_sort_values() -> None:
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
            await repo.create(
                id="a",
                name="first",
                created_at=datetime(2026, 1, 1, tzinfo=UTC),
                event_date=date(2026, 1, 1),
                amount=Decimal("1.25"),
                uuid_value=uuid.UUID("00000000-0000-0000-0000-000000000001"),
                binary_value=b"a",
            )
            await repo.create(
                id="b",
                name="second",
                created_at=datetime(2026, 1, 2, tzinfo=UTC),
                event_date=date(2026, 1, 2),
                amount=Decimal("2.50"),
                uuid_value=uuid.UUID("00000000-0000-0000-0000-000000000002"),
                binary_value=b"b",
            )

            for order_by in ("created_at", "event_date", "amount", "uuid_value", "binary_value"):
                first = await repo.paginate(limit=1, order_by=order_by)
                assert [item.id for item in first.items] == ["a"]
                assert first.next_cursor is not None

                second = await repo.paginate(cursor=first.next_cursor, limit=1, order_by=order_by)
                assert [item.id for item in second.items] == ["b"]
                assert second.has_more is False
    finally:
        await manager.close()
