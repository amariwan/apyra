import asyncio
import base64
import json
import os
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import cast

import pytest
from sqlalchemy import Date, DateTime, LargeBinary, Numeric, String, Uuid, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import Mapped, mapped_column

from apyra.db import (
    Base,
    DatabaseManager,
    DbSettings,
    Repository,
    TenantScopedMixin,
    TenantScopedRepository,
    build_async_database_url,
)


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


class TenantItem(Base, TenantScopedMixin):
    __tablename__ = "tenant_items"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)


class CompositeTenantItem(Base):
    __tablename__ = "composite_tenant_items"
    tenant_id: Mapped[str] = mapped_column(String, primary_key=True)
    item_id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)


POSTGRES_URL = os.getenv(
    "APYRA_TEST_POSTGRES_URL", "postgresql+asyncpg://apyra:apyra@localhost:5432/apyra_test"
)


def _postgres_available() -> bool:
    async def check() -> bool:
        engine = create_async_engine(POSTGRES_URL)
        try:
            async with engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
            return True
        except Exception:  # noqa: BLE001 - used to decide whether the integration test can run
            return False
        finally:
            await engine.dispose()

    return asyncio.run(check())


@pytest.mark.asyncio
async def test_cursor_pagination_rejects_oversized_cursor_json() -> None:
    payload = json.dumps(["x" * 20_000]).encode("utf-8")
    cursor = base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")
    repository = Repository(cast(AsyncSession, object()), Item)

    with pytest.raises(ValueError, match="cursor is invalid"):
        await repository.paginate(cursor=cursor)


@pytest.mark.asyncio
async def test_tenant_scoped_repository_isolates_tenants() -> None:
    settings = DbSettings(db_enabled=True, db_backend="sqlite", db_database=":memory:")
    manager = DatabaseManager(build_async_database_url(settings), engine_kwargs={"echo": False})
    try:
        await manager._ensure_current_loop()
        engine = manager.engine
        assert engine is not None
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with manager.session() as session:
            base = Repository(session, TenantItem)
            await base.create(id="a1", name="alpha", tenant_id="tenant-a")
            await base.create(id="b1", name="beta", tenant_id="tenant-b")

            repo_a = TenantScopedRepository(session, TenantItem, "tenant-a")
            # list(), count(), and get()-by-id are all restricted to tenant-a.
            assert [item.id for item in await repo_a.list()] == ["a1"]
            assert await repo_a.count() == 1
            assert await repo_a.get("b1") is None
            fetched = await repo_a.get("a1")
            assert fetched is not None and fetched.name == "alpha"

            await base.create(id="tenant-a-row", name="alpha row", tenant_id="tenant-a")
            await base.create(id="tenant-b-row", name="beta row", tenant_id="tenant-b")
            assert await repo_a.create(id="scoped", name="scoped row")
            with pytest.raises(ValueError, match="another tenant"):
                await repo_a.create(id="injected", name="injected", tenant_id="tenant-b")

            tenant_b = await base.get("b1")
            assert tenant_b is not None
            with pytest.raises(ValueError, match="another tenant"):
                await repo_a.update(tenant_b, name="hijacked")
            with pytest.raises(ValueError, match="another tenant"):
                await repo_a.delete(tenant_b)

            stale_update = await base.create(id="stale-update", name="before", tenant_id="tenant-a")
            stale_delete = await base.create(id="stale-delete", name="before", tenant_id="tenant-a")
            await session.execute(
                update(TenantItem)
                .where(TenantItem.id.in_((stale_update.id, stale_delete.id)))
                .values(tenant_id="tenant-b")
                .execution_options(synchronize_session=False)
            )
            with pytest.raises(ValueError, match="no longer owned"):
                await repo_a.update(stale_update, name="must-not-update")
            with pytest.raises(ValueError, match="no longer owned"):
                await repo_a.delete(stale_delete)

            persisted_rows = (
                await session.execute(
                    select(TenantItem.id, TenantItem.tenant_id).where(
                        TenantItem.id.in_((stale_update.id, stale_delete.id))
                    )
                )
            ).all()
            assert set(persisted_rows) == {
                ("stale-update", "tenant-b"),
                ("stale-delete", "tenant-b"),
            }

        async with manager.session() as session:
            base = Repository(session, CompositeTenantItem)
            await base.create(tenant_id="tenant-a", item_id="shared", name="alpha")
            await base.create(tenant_id="tenant-b", item_id="shared", name="beta")
            repo_a = TenantScopedRepository(session, CompositeTenantItem, "tenant-a")
            assert await repo_a.get(("tenant-b", "shared")) is None
            tenant_a_row = await repo_a.get(("tenant-a", "shared"))
            assert tenant_a_row is not None and tenant_a_row.name == "alpha"
            assert await repo_a.get({"tenant_id": "tenant-b", "item_id": "shared"}) is None
    finally:
        await manager.close()


@pytest.mark.asyncio
@pytest.mark.postgres
@pytest.mark.skipif(not _postgres_available(), reason="PostgreSQL unavailable")
async def test_tenant_owner_lock_blocks_concurrent_transfer() -> None:
    engine = create_async_engine(POSTGRES_URL)
    schema = f"tenant_lock_{uuid.uuid4().hex}"
    try:
        async with engine.begin() as connection:
            await connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
            await connection.exec_driver_sql(f'SET search_path TO "{schema}"')
            await connection.run_sync(Base.metadata.create_all)

        async with AsyncSession(engine, expire_on_commit=False) as session:
            await session.execute(text(f'SET search_path TO "{schema}"'))
            session.add(TenantItem(id="locked-row", name="before", tenant_id="tenant-a"))
            await session.commit()

        async with (
            AsyncSession(engine, expire_on_commit=False) as owner_session,
            AsyncSession(engine, expire_on_commit=False) as transfer_session,
        ):
            await owner_session.execute(text(f'SET search_path TO "{schema}"'))
            await transfer_session.execute(text(f'SET search_path TO "{schema}"'))
            repository = TenantScopedRepository(owner_session, TenantItem, "tenant-a")
            instance = await repository.get("locked-row")
            assert instance is not None
            await repository.update(instance, name="updated")

            async def transfer_ownership() -> None:
                await transfer_session.execute(
                    update(TenantItem)
                    .where(TenantItem.id == "locked-row")
                    .values(tenant_id="tenant-b")
                    .execution_options(synchronize_session=False)
                )

            transfer = asyncio.create_task(transfer_ownership())
            try:
                await asyncio.sleep(0.1)
                assert not transfer.done(), "tenant transfer bypassed the row ownership lock"
                await owner_session.commit()
                await asyncio.wait_for(transfer, timeout=5)
                await transfer_session.commit()
            finally:
                if not transfer.done():
                    transfer.cancel()
                    with pytest.raises(asyncio.CancelledError):
                        await transfer
    finally:
        async with engine.begin() as connection:
            await connection.exec_driver_sql(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        await engine.dispose()


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
