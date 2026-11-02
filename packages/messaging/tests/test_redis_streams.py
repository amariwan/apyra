from __future__ import annotations

import asyncio
import contextlib
import os
import uuid
from typing import Any

import pytest
import redis.asyncio as redis_async

from apyra.messaging.contracts import DeliveryContext, MessageEnvelope
from apyra.messaging.idempotency import RedisIdempotencyStore
from apyra.messaging.redis_streams import RedisStreamsConsumer, RedisStreamsPublisher
from apyra.messaging.retry import ExponentialBackoff


def _redis_url() -> str:
    return os.getenv("APYRA_TEST_REDIS_URL", "redis://localhost:6379/15")


def _redis_available() -> bool:
    import asyncio

    async def check() -> bool:
        try:
            client = redis_async.from_url(_redis_url())
            await client.ping()
            await client.aclose()
            return True
        except Exception:  # noqa: BLE001
            return False

    return asyncio.run(check())


pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.redis,
    pytest.mark.skipif(not _redis_available(), reason="Redis unavailable"),
]


class _Handler:
    def __init__(self, *, fail: bool = False) -> None:
        self.received: list[uuid.UUID] = []
        self.attempts: list[int] = []
        self.fail = fail

    async def handle(self, envelope: MessageEnvelope, context: DeliveryContext) -> None:
        if self.fail:
            raise RuntimeError("boom")
        self.received.append(envelope.message_id)
        self.attempts.append(context.attempt)


async def _make_client() -> Any:
    return redis_async.from_url(_redis_url(), decode_responses=True)


async def test_redis_publish_and_consume() -> None:
    client = await _make_client()
    await client.flushdb()
    stream, group, consumer_name = "test-stream", "test-group", "consumer-1"
    handler = _Handler()
    publisher = RedisStreamsPublisher(client, stream)
    envelope = MessageEnvelope(payload={"hello": "world"})
    await publisher.publish(envelope)

    consumer = RedisStreamsConsumer(client, stream, group, consumer_name, handler)
    await consumer.ensure_group()
    response = await client.xreadgroup(
        groupname=group,
        consumername=consumer_name,
        streams={stream: ">"},
        count=10,
        block=100,
    )
    assert response
    for _, messages in response:
        for message_id, fields in messages:
            env = MessageEnvelope(
                message_id=uuid.UUID(fields["message_id"]),
                payload=__import__("json").loads(fields["payload"]),
            )
            ctx = DeliveryContext(message_id=env.message_id, attempt=1, consumer=consumer_name)
            await handler.handle(env, ctx)
            await client.xack(stream, group, message_id)
    assert envelope.message_id in handler.received
    await client.flushdb()
    await client.aclose()


async def test_consumer_run_processes_messages() -> None:
    client = await _make_client()
    await client.flushdb()
    stream, group = "run-stream", "run-group"
    handler = _Handler()
    publisher = RedisStreamsPublisher(client, stream)
    envelope = MessageEnvelope(payload={"n": 1})
    await publisher.publish(envelope)

    consumer = RedisStreamsConsumer(client, stream, group, "worker", handler, block_ms=50)
    task = asyncio.create_task(consumer.run())
    try:
        for _ in range(50):
            if envelope.message_id in handler.received:
                break
            await asyncio.sleep(0.05)
        consumer.stop()
        await task
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
    assert envelope.message_id in handler.received
    # The message must be acknowledged (no pending entries remain).
    pending = await client.xpending(stream, group)
    assert pending["pending"] == 0
    await client.flushdb()
    await client.aclose()


async def test_recover_pending_processes_abandoned_messages() -> None:
    client = await _make_client()
    await client.flushdb()
    stream, group = "rec-stream", "rec-group"
    publisher = RedisStreamsPublisher(client, stream)
    envelope = MessageEnvelope(payload={"n": 1})
    await publisher.publish(envelope)

    # Consumer A delivers the message then "crashes" without acknowledging it.
    consumer_a = RedisStreamsConsumer(client, stream, group, "worker-a", _Handler())
    await consumer_a.ensure_group()
    response = await client.xreadgroup(
        groupname=group, consumername="worker-a", streams={stream: ">"}, count=10, block=100
    )
    assert response

    # Consumer B recovers and processes the abandoned message.
    handler_b = _Handler()
    consumer_b = RedisStreamsConsumer(client, stream, group, "worker-b", handler_b, min_idle_ms=0)
    processed = await consumer_b.recover_pending()
    assert processed == 1
    assert envelope.message_id in handler_b.received
    assert handler_b.attempts == [2]  # second delivery attempt
    await client.flushdb()
    await client.aclose()


async def test_failed_message_is_dead_lettered_after_exhaustion() -> None:
    client = await _make_client()
    await client.flushdb()
    stream, group, dlq = "dl-stream", "dl-group", "dl-stream-dead"
    publisher = RedisStreamsPublisher(client, stream)
    envelope = MessageEnvelope(payload={"n": 1})
    await publisher.publish(envelope)

    consumer = RedisStreamsConsumer(
        client,
        stream,
        group,
        "worker",
        _Handler(fail=True),
        retry_policy=ExponentialBackoff(max_attempts=1, jitter=False),
        dead_letter_stream=dlq,
        min_idle_ms=0,
    )
    await consumer.ensure_group()
    # First delivery fails (left pending with delivery count 1).
    response = await client.xreadgroup(
        groupname=group, consumername="worker", streams={stream: ">"}, count=10, block=100
    )
    assert response
    for _, messages in response:
        for message_id, fields in messages:
            await consumer._process(message_id, fields, attempt=1)

    # Recovery sees delivery count >= max_attempts and moves it to the DLQ.
    await consumer.recover_pending()

    dead = await client.xrange(dlq, min="-", max="+")
    assert len(dead) == 1
    assert dead[0][1]["message_id"] == str(envelope.message_id)
    # Source stream entry removed after dead-lettering.
    remaining = await client.xrange(stream, min="-", max="+")
    assert remaining == []
    await client.flushdb()
    await client.aclose()


async def test_idempotency_suppresses_duplicate_delivery() -> None:
    client = await _make_client()
    await client.flushdb()
    stream, group = "idem-stream", "idem-group"
    store = RedisIdempotencyStore(client)
    publisher = RedisStreamsPublisher(client, stream)
    handler = _Handler()

    message_id = uuid.uuid4()
    envelope = MessageEnvelope(message_id=message_id, payload={"n": 1})
    await publisher.publish(envelope)
    # Publish the same logical message again (duplicate delivery).
    await publisher.publish(envelope)

    consumer = RedisStreamsConsumer(
        client, stream, group, "worker", handler, idempotency_store=store
    )
    await consumer.ensure_group()
    response = await client.xreadgroup(
        groupname=group, consumername="worker", streams={stream: ">"}, count=10, block=100
    )
    assert response
    for _, messages in response:
        for entry_id, fields in messages:
            await consumer._process(entry_id, fields, attempt=1)

    assert len(handler.received) == 1
    assert handler.received[0] == message_id
    await client.flushdb()
    await client.aclose()
