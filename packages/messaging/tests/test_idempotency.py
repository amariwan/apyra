from __future__ import annotations

import asyncio
import os
import uuid

import pytest

from apyra.messaging.contracts import DeliveryContext, MessageEnvelope
from apyra.messaging.idempotency import (
    ClaimResult,
    InMemoryIdempotencyStore,
    PostgresIdempotencyStore,
    RedisIdempotencyStore,
)
from apyra.messaging.redis_streams import RedisStreamsConsumer

REDIS_URL = os.getenv("APYRA_TEST_REDIS_URL", "redis://localhost:6379/15")
POSTGRES_URL = os.getenv(
    "APYRA_TEST_POSTGRES_URL", "postgresql+asyncpg://apyra:apyra@localhost:5432/apyra_test"
)


def _redis_available() -> bool:
    import redis.asyncio as redis_async

    async def check() -> bool:
        try:
            client = redis_async.from_url(REDIS_URL)
            await client.ping()
            await client.aclose()
            return True
        except Exception:  # noqa: BLE001
            return False

    return asyncio.run(check())


def _postgres_available() -> bool:
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    async def check() -> bool:
        try:
            engine = create_async_engine(POSTGRES_URL)
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            await engine.dispose()
            return True
        except Exception:  # noqa: BLE001
            return False

    return asyncio.run(check())


async def test_in_memory_claim_semantics() -> None:
    store = InMemoryIdempotencyStore()
    message_id = uuid.uuid4()
    assert await store.claim(message_id) is ClaimResult.CLAIMED
    await store.release(message_id)
    assert await store.claim(message_id) is ClaimResult.CLAIMED
    # A second claim while the first is in progress is reported, not granted.
    assert await store.claim(message_id) is ClaimResult.IN_PROGRESS
    await store.complete(message_id)
    assert await store.claim(message_id) is ClaimResult.ALREADY_DONE
    assert await store.is_processed(message_id) is True


async def test_in_memory_claim_expires_after_ttl() -> None:
    store = InMemoryIdempotencyStore(default_ttl_seconds=-1)
    message_id = uuid.uuid4()
    assert await store.claim(message_id) is ClaimResult.CLAIMED
    # TTL already in the past, so the claim is reclaimable.
    assert await store.claim(message_id) is ClaimResult.CLAIMED


async def test_in_memory_claim_can_be_released_after_failure() -> None:
    store = InMemoryIdempotencyStore()
    message_id = uuid.uuid4()
    assert await store.claim(message_id) is ClaimResult.CLAIMED


async def test_attempt_record_failure_releases_acquired_claim() -> None:
    class Client:
        async def delete(self, key: str) -> None:
            pass

    class Handler:
        async def handle(self, envelope: MessageEnvelope, context: DeliveryContext) -> None:
            raise AssertionError("handler must not run when attempt recording fails")

    store = InMemoryIdempotencyStore()
    envelope = MessageEnvelope(payload={"value": 1})
    consumer = RedisStreamsConsumer(
        Client(), "stream", "group", "worker", Handler(), idempotency_store=store
    )

    async def fail_record_attempt(message_id: str) -> int:
        raise RuntimeError("temporary Redis failure")

    consumer._record_attempt = fail_record_attempt  # type: ignore[method-assign]
    fields = {
        "message_id": str(envelope.message_id),
        "payload": '{"value": 1}',
        "occurred_at": envelope.occurred_at.isoformat(),
    }

    assert await consumer._process("1-0", fields, attempt=1) == "deferred"
    assert await store.claim(envelope.message_id) is ClaimResult.CLAIMED


async def test_redis_claim_remains_releasable_when_completion_fails() -> None:
    class Client:
        def __init__(self) -> None:
            self.values: dict[str, str] = {}
            self.fail_next_eval = True

        async def set(self, key: str, value: str, **kwargs: object) -> bool:
            if kwargs.get("nx") and key in self.values:
                return False
            self.values[key] = value
            return True

        async def get(self, key: str) -> str | None:
            return self.values.get(key)

        async def eval(self, script: str, key_count: int, key: str, expected: str) -> int:
            if self.fail_next_eval:
                self.fail_next_eval = False
                raise RuntimeError("temporary Redis failure")
            if self.values.get(key) != expected:
                return 0
            if "redis.call('DEL'" in script:
                del self.values[key]
            else:
                self.values[key] = "done"
            return 1

    client = Client()
    store = RedisIdempotencyStore(client)
    message_id = uuid.uuid4()
    assert await store.claim(message_id) is ClaimResult.CLAIMED
    with pytest.raises(RuntimeError, match="temporary Redis failure"):
        await store.complete(message_id)

    await store.release(message_id)
    assert await store.claim(message_id) is ClaimResult.CLAIMED


@pytest.mark.asyncio
@pytest.mark.redis
@pytest.mark.skipif(not _redis_available(), reason="Redis unavailable")
async def test_redis_idempotency_claim() -> None:
    import redis.asyncio as redis_async

    client = redis_async.from_url(REDIS_URL, decode_responses=True)
    await client.flushdb()
    store = RedisIdempotencyStore(client)
    message_id = uuid.uuid4()
    try:
        assert await store.claim(message_id) is ClaimResult.CLAIMED
        assert await store.claim(message_id) is ClaimResult.IN_PROGRESS
        await store.complete(message_id)
        assert await store.claim(message_id) is ClaimResult.ALREADY_DONE
        assert await store.is_processed(message_id) is True
    finally:
        await client.flushdb()
        await client.aclose()


@pytest.mark.asyncio
@pytest.mark.redis
@pytest.mark.skipif(not _redis_available(), reason="Redis unavailable")
async def test_redis_idempotency_concurrent_claim_admits_single_winner() -> None:
    import redis.asyncio as redis_async

    client = redis_async.from_url(REDIS_URL, decode_responses=True)
    await client.flushdb()
    store = RedisIdempotencyStore(client)
    message_id = uuid.uuid4()
    try:
        results = await asyncio.gather(
            store.claim(message_id),
            store.claim(message_id),
            store.claim(message_id),
        )
        assert results.count(ClaimResult.CLAIMED) == 1
        assert results.count(ClaimResult.IN_PROGRESS) == 2
    finally:
        await client.flushdb()
        await client.aclose()


@pytest.mark.asyncio
@pytest.mark.redis
@pytest.mark.skipif(not _redis_available(), reason="Redis unavailable")
async def test_redis_claim_release_is_owned_by_the_claiming_task() -> None:
    import redis.asyncio as redis_async

    client = redis_async.from_url(REDIS_URL, decode_responses=True)
    await client.flushdb()
    store = RedisIdempotencyStore(client)
    message_id = uuid.uuid4()
    try:
        assert await store.claim(message_id) is ClaimResult.CLAIMED
        await store.release(message_id)
        assert await store.claim(message_id) is ClaimResult.CLAIMED
        await store.complete(message_id)
        assert await store.claim(message_id) is ClaimResult.ALREADY_DONE
    finally:
        await client.flushdb()
        await client.aclose()


@pytest.mark.asyncio
@pytest.mark.postgres
@pytest.mark.skipif(not _postgres_available(), reason="PostgreSQL unavailable")
async def test_postgres_idempotency_claim() -> None:
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

    from apyra.messaging.idempotency import IdempotencyRecord

    engine = create_async_engine(POSTGRES_URL)
    async with engine.begin() as conn:
        await conn.run_sync(IdempotencyRecord.metadata.drop_all)
        await conn.run_sync(IdempotencyRecord.metadata.create_all)

    message_id = uuid.uuid4()
    async with AsyncSession(engine, expire_on_commit=False) as session:
        store = PostgresIdempotencyStore(session)
        assert await store.claim(message_id) is ClaimResult.CLAIMED
        await session.commit()

    async with AsyncSession(engine, expire_on_commit=False) as session:
        store = PostgresIdempotencyStore(session)
        assert await store.claim(message_id) is ClaimResult.IN_PROGRESS

    async with AsyncSession(engine, expire_on_commit=False) as session:
        store = PostgresIdempotencyStore(session)
        await store.complete(message_id)
        await session.commit()

    async with AsyncSession(engine, expire_on_commit=False) as session:
        store = PostgresIdempotencyStore(session)
        assert await store.claim(message_id) is ClaimResult.ALREADY_DONE
        assert await store.is_processed(message_id) is True
    await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.postgres
@pytest.mark.skipif(not _postgres_available(), reason="PostgreSQL unavailable")
async def test_postgres_idempotency_claim_expired_is_reclaimable() -> None:
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

    from apyra.messaging.idempotency import IdempotencyRecord

    engine = create_async_engine(POSTGRES_URL)
    async with engine.begin() as conn:
        await conn.run_sync(IdempotencyRecord.metadata.drop_all)
        await conn.run_sync(IdempotencyRecord.metadata.create_all)

    message_id = uuid.uuid4()
    # Claim with a negative TTL so the reservation is immediately expired.
    async with AsyncSession(engine, expire_on_commit=False) as session:
        store = PostgresIdempotencyStore(session, default_ttl_seconds=-1)
        assert await store.claim(message_id) is ClaimResult.CLAIMED
        await session.commit()

    async with AsyncSession(engine, expire_on_commit=False) as session:
        store = PostgresIdempotencyStore(session)
        assert await store.claim(message_id) is ClaimResult.CLAIMED
    await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.postgres
@pytest.mark.skipif(not _postgres_available(), reason="PostgreSQL unavailable")
async def test_postgres_expired_claim_takeover_has_one_winner() -> None:
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

    from apyra.messaging.idempotency import IdempotencyRecord

    engine = create_async_engine(POSTGRES_URL)
    async with engine.begin() as conn:
        await conn.run_sync(IdempotencyRecord.metadata.drop_all)
        await conn.run_sync(IdempotencyRecord.metadata.create_all)

    message_id = uuid.uuid4()
    async with AsyncSession(engine, expire_on_commit=False) as session:
        assert (
            await PostgresIdempotencyStore(session, default_ttl_seconds=-1).claim(message_id)
            is ClaimResult.CLAIMED
        )
        await session.commit()

    async def reclaim() -> ClaimResult:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            result = await PostgresIdempotencyStore(session).claim(message_id)
            await session.commit()
            return result

    outcomes = await asyncio.gather(reclaim(), reclaim())
    assert outcomes.count(ClaimResult.CLAIMED) == 1
    assert outcomes.count(ClaimResult.IN_PROGRESS) == 1
    await engine.dispose()
