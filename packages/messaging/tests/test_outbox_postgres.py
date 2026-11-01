from __future__ import annotations

import asyncio
import os

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from apyra.messaging.outbox import OutboxMessage, OutboxRepository

DATABASE_URL = os.getenv("APYRA_TEST_POSTGRES_URL", "postgresql+asyncpg:///apyra_test")


def _postgres_available() -> bool:
    try:
        from sqlalchemy.ext.asyncio import create_async_engine

        async def check() -> bool:
            try:
                engine = create_async_engine(DATABASE_URL)
                async with engine.connect() as conn:
                    await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
                await engine.dispose()
                return True
            except Exception:  # noqa: BLE001
                return False

        return asyncio.run(check())
    except Exception:  # noqa: BLE001
        return False


pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.postgres,
    pytest.mark.skipif(not _postgres_available(), reason="PostgreSQL unavailable"),
]


async def _create_tables(engine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(OutboxMessage.metadata.drop_all)
        await conn.run_sync(OutboxMessage.metadata.create_all)


async def test_outbox_atomic_commit_and_rollback() -> None:
    engine = create_async_engine(DATABASE_URL)
    await _create_tables(engine)

    async with AsyncSession(engine, expire_on_commit=False) as session:
        repo = OutboxRepository(session)
        message = await repo.add("topic", {"value": 1})
        await session.commit()
        assert message.status == "pending"

    async with AsyncSession(engine, expire_on_commit=False) as session:
        repo = OutboxRepository(session)
        await repo.add("topic", {"value": 2})
        await session.rollback()

    async with AsyncSession(engine, expire_on_commit=False) as session:
        result = await session.execute(select(OutboxMessage))
        messages = list(result.scalars().all())
        assert len(messages) == 1
    await engine.dispose()


async def test_outbox_claim_and_deliver() -> None:
    engine = create_async_engine(DATABASE_URL)
    await _create_tables(engine)

    async with AsyncSession(engine, expire_on_commit=False) as session:
        repo = OutboxRepository(session)
        message = await repo.add("topic", {"value": 3})
        await session.commit()

    async with AsyncSession(engine, expire_on_commit=False) as session:
        repo = OutboxRepository(session)
        claimed = await repo.claim("worker-1", 10, 30)
        assert len(claimed) == 1
        assert claimed[0].id == message.id
        await repo.mark_delivered(claimed[0])
        await session.commit()
        assert claimed[0].status == "delivered"
    await engine.dispose()
