from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm.exc import StaleDataError

from apyra.messaging.outbox import (
    InvalidStateTransitionError,
    OutboxMessage,
    OutboxRepository,
)

DATABASE_URL = os.getenv(
    "APYRA_TEST_POSTGRES_URL", "postgresql+asyncpg://apyra:apyra@localhost:5432/apyra_test"
)


def _postgres_available() -> bool:
    from sqlalchemy import text

    async def check() -> bool:
        try:
            engine = create_async_engine(DATABASE_URL)
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            await engine.dispose()
            return True
        except Exception:  # noqa: BLE001
            return False

    return asyncio.run(check())


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
        assert len(list(result.scalars().all())) == 1
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
        assert claimed[0].leased_by == "worker-1"
        assert claimed[0].fencing_token is not None
        await repo.mark_delivered(claimed[0])
        await session.commit()
        assert claimed[0].status == "delivered"
    await engine.dispose()


async def test_stale_worker_cannot_overwrite_state() -> None:
    engine = create_async_engine(DATABASE_URL)
    await _create_tables(engine)

    # Session A adds and claims the message (worker-1).
    session_a = AsyncSession(engine, expire_on_commit=False)
    repo_a = OutboxRepository(session_a)
    await repo_a.add("topic", {"value": 1})
    await session_a.commit()
    (claimed,) = await repo_a.claim("worker-1", 10, 30)
    # Expire the lease immediately so another worker can take it over.
    claimed.lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
    await session_a.commit()

    # Session B recovers the expired lease and reclaims it (worker-2).
    async with AsyncSession(engine, expire_on_commit=False) as session_b:
        repo_b = OutboxRepository(session_b)
        assert await repo_b.recover_expired_leases() == 1
        (reclaimed,) = await repo_b.claim("worker-2", 10, 30)
        assert reclaimed.leased_by == "worker-2"
        await session_b.commit()

    # Stale worker-1 (session A) attempts to deliver; version_id must reject it.
    with pytest.raises(StaleDataError):
        await repo_a.mark_delivered(claimed)
        await session_a.commit()

    await session_a.close()
    await engine.dispose()


async def test_concurrent_claim_skips_locked_rows() -> None:
    engine = create_async_engine(DATABASE_URL)
    await _create_tables(engine)

    async with AsyncSession(engine, expire_on_commit=False) as session:
        repo = OutboxRepository(session)
        await repo.add("topic", {"value": 1})
        await repo.add("topic", {"value": 2})
        await session.commit()

    session_a = AsyncSession(engine, expire_on_commit=False)
    session_b = AsyncSession(engine, expire_on_commit=False)
    try:
        # Session A claims both rows and holds the locks (uncommitted).
        claimed_a = await OutboxRepository(session_a).claim("worker-a", 10, 30)
        assert len(claimed_a) == 2
        # Session B cannot claim the locked rows.
        claimed_b = await OutboxRepository(session_b).claim("worker-b", 10, 30)
        assert claimed_b == []
    finally:
        await session_a.close()
        await session_b.close()
    await engine.dispose()


async def test_invalid_state_transition_rejected() -> None:
    engine = create_async_engine(DATABASE_URL)
    await _create_tables(engine)

    async with AsyncSession(engine, expire_on_commit=False) as session:
        repo = OutboxRepository(session)
        await repo.add("topic", {"value": 1})
        await session.commit()
        (claimed,) = await repo.claim("worker-1", 10, 30)
        await repo.mark_delivered(claimed)
        with pytest.raises(InvalidStateTransitionError):
            await repo.mark_delivered(claimed)
    await engine.dispose()


async def test_mark_failed_dead_letters_after_max_attempts() -> None:
    engine = create_async_engine(DATABASE_URL)
    await _create_tables(engine)

    async with AsyncSession(engine, expire_on_commit=False) as session:
        repo = OutboxRepository(session)
        await repo.add("topic", {"value": 1})
        await session.commit()

        (claimed,) = await repo.claim("worker-1", 10, 30)
        await repo.mark_failed(claimed, "boom", retry_delay_seconds=0.0, max_attempts=1)
        await session.commit()
        assert claimed.status == "dead_letter"

    async with AsyncSession(engine, expire_on_commit=False) as session:
        result = await session.execute(select(OutboxMessage))
        message = result.scalars().one()
        assert message.status == "dead_letter"
        assert message.last_error == "boom"
    await engine.dispose()
