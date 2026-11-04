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
    assert handler_b.attempts == [1]  # the first handler attempt after the abandoned read
    await client.flushdb()
    await client.aclose()


async def test_recover_pending_scans_past_recent_entries() -> None:
    client = await _make_client()
    await client.flushdb()
    stream, group = "paged-rec-stream", "paged-rec-group"
    publisher = RedisStreamsPublisher(client, stream)
    older = MessageEnvelope(payload={"n": 1})
    newer = MessageEnvelope(payload={"n": 2})
    await publisher.publish(older)
    await publisher.publish(newer)

    consumer = RedisStreamsConsumer(
        client,
        stream,
        group,
        "worker-a",
        _Handler(),
        min_idle_ms=30,
        recover_batch_size=1,
    )
    await consumer.ensure_group()
    deliveries = await client.xreadgroup(
        groupname=group, consumername="worker-a", streams={stream: ">"}, count=2
    )
    assert deliveries
    first_entry_id = deliveries[0][1][0][0]
    await asyncio.sleep(0.04)
    # Refresh the first (lowest-ID) entry so it is too recent, while the later
    # entry remains eligible and would be starved by a first-page-only scan.
    await client.xclaim(stream, group, "worker-a", min_idle_time=0, message_ids=[first_entry_id])

    handler = _Handler()
    recovering = RedisStreamsConsumer(
        client,
        stream,
        group,
        "worker-b",
        handler,
        min_idle_ms=30,
        recover_batch_size=1,
    )
    assert await recovering.recover_pending() == 0
    processed = await recovering.recover_pending()

    assert processed == 1
    assert handler.received == [newer.message_id]
    pending = await client.xpending_range(stream, group, min="-", max="+", count=10)
    assert [entry["message_id"] for entry in pending] == [first_entry_id]
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
        retry_policy=ExponentialBackoff(max_attempts=1, base_delay_seconds=0.001, jitter=False),
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

    # Wait for the configured retry delay before checking exhausted attempts.
    await asyncio.sleep(0.01)
    await consumer.recover_pending()

    dead = await client.xrange(dlq, min="-", max="+")
    assert len(dead) == 1
    assert dead[0][1]["message_id"] == str(envelope.message_id)
    # The source entry remains available to other consumer groups.
    remaining = await client.xrange(stream, min="-", max="+")
    assert len(remaining) == 1
    await client.flushdb()
    await client.aclose()


async def test_exhausted_message_without_dead_letter_sink_remains_pending() -> None:
    client = await _make_client()
    await client.flushdb()
    stream, group = "no-dlq-stream", "no-dlq-group"
    envelope = MessageEnvelope(payload={"n": 1})
    await RedisStreamsPublisher(client, stream).publish(envelope)

    consumer = RedisStreamsConsumer(
        client,
        stream,
        group,
        "worker",
        _Handler(fail=True),
        retry_policy=ExponentialBackoff(max_attempts=1, base_delay_seconds=0.001, jitter=False),
        min_idle_ms=0,
    )
    await consumer.ensure_group()
    response = await client.xreadgroup(
        groupname=group, consumername="worker", streams={stream: ">"}, count=1, block=100
    )
    assert response
    entry_id, fields = response[0][1][0]
    assert await consumer._process(entry_id, fields, attempt=1) == "failed"

    await asyncio.sleep(0.01)
    await consumer.recover_pending()

    assert (await client.xpending(stream, group))["pending"] == 1
    assert len(await client.xrange(stream, min="-", max="+")) == 1
    await client.flushdb()
    await client.aclose()


async def test_invalid_message_is_preserved_in_dead_letter_stream(
    caplog: pytest.LogCaptureFixture,
) -> None:
    client = await _make_client()
    await client.flushdb()
    stream, group, dlq = "invalid-stream", "invalid-group", "invalid-stream-dead"
    entry_id = await client.xadd(
        stream,
        {
            "message_id": "invalid-id",
            "payload": "password=do-not-log",
            "occurred_at": "not-a-datetime",
        },
    )
    consumer = RedisStreamsConsumer(
        client, stream, group, "worker", _Handler(), dead_letter_stream=dlq
    )
    await consumer.ensure_group()
    response = await client.xreadgroup(
        groupname=group, consumername="worker", streams={stream: ">"}, count=1, block=100
    )
    assert response

    with caplog.at_level("ERROR", logger="apyra.messaging.redis_streams"):
        result = await consumer._process(entry_id, response[0][1][0][1], attempt=1)

    dead = await client.xrange(dlq, min="-", max="+")
    assert result == "invalid"
    assert len(dead) == 1
    assert dead[0][1]["payload"] == "password=do-not-log"
    assert dead[0][1]["apyra_error"] == "invalid_message_payload"
    assert dead[0][1]["apyra_decode_error"] == "ValueError"
    assert "do-not-log" not in caplog.text
    assert (await client.xpending(stream, group))["pending"] == 0
    await client.flushdb()
    await client.aclose()


async def test_handler_exception_log_excludes_exception_text(
    caplog: pytest.LogCaptureFixture,
) -> None:
    client = await _make_client()
    await client.flushdb()
    stream, group = "safe-log-stream", "safe-log-group"
    envelope = MessageEnvelope(payload={"n": 1})
    await RedisStreamsPublisher(client, stream).publish(envelope)
    ((entry_id, _fields),) = await client.xrange(stream, min="-", max="+")

    class SensitiveErrorHandler:
        async def handle(self, envelope: MessageEnvelope, context: DeliveryContext) -> None:
            raise RuntimeError("password=do-not-log")

    consumer = RedisStreamsConsumer(client, stream, group, "worker", SensitiveErrorHandler())
    await consumer.ensure_group()
    response = await client.xreadgroup(
        groupname=group, consumername="worker", streams={stream: ">"}, count=1, block=100
    )
    assert response

    with caplog.at_level("WARNING", logger="apyra.messaging.redis_streams"):
        result = await consumer._process(entry_id, response[0][1][0][1], attempt=1)

    assert result == "failed"
    assert "do-not-log" not in caplog.text
    assert any(getattr(record, "error_type", None) == "RuntimeError" for record in caplog.records)
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


async def test_failed_handler_releases_idempotency_claim_for_retry() -> None:
    client = await _make_client()
    await client.flushdb()
    stream, group = "retry-idem-stream", "retry-idem-group"
    store = RedisIdempotencyStore(client)

    class RetryOnceHandler:
        def __init__(self) -> None:
            self.calls = 0

        async def handle(self, envelope: MessageEnvelope, context: DeliveryContext) -> None:
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("transient failure")

    handler = RetryOnceHandler()
    envelope = MessageEnvelope(payload={"n": 1})
    await RedisStreamsPublisher(client, stream).publish(envelope)
    consumer = RedisStreamsConsumer(
        client, stream, group, "worker", handler, idempotency_store=store
    )
    await consumer.ensure_group()
    response = await client.xreadgroup(
        groupname=group, consumername="worker", streams={stream: ">"}, count=1, block=100
    )
    entry_id, fields = response[0][1][0]

    assert await consumer._process(entry_id, fields, attempt=1) == "failed"
    assert await consumer._process(entry_id, fields, attempt=2) == "acked"
    assert handler.calls == 2
    await client.flushdb()
    await client.aclose()


async def test_recovered_entry_stays_pending_until_idempotency_claim_is_free() -> None:
    client = await _make_client()
    await client.flushdb()
    stream, group = "deferred-idem-stream", "deferred-idem-group"
    store = RedisIdempotencyStore(client)
    envelope = MessageEnvelope(payload={"n": 1})
    await RedisStreamsPublisher(client, stream).publish(envelope)
    handler = _Handler()
    consumer = RedisStreamsConsumer(
        client, stream, group, "worker", handler, idempotency_store=store, min_idle_ms=0
    )
    await consumer.ensure_group()
    response = await client.xreadgroup(
        groupname=group, consumername="worker", streams={stream: ">"}, count=1, block=100
    )
    entry_id, fields = response[0][1][0]
    claimed = asyncio.Event()
    release = asyncio.Event()

    async def hold_claim() -> None:
        assert (await store.claim(envelope.message_id)).value == "claimed"
        claimed.set()
        await release.wait()
        await store.release(envelope.message_id)

    owner_task = asyncio.create_task(hold_claim())
    await claimed.wait()
    try:
        assert await consumer._process(entry_id, fields, attempt=1) == "in_progress"
        pending = await client.xpending(stream, group)
        assert pending["pending"] == 1
    finally:
        release.set()
        await owner_task
    assert await consumer.recover_pending() == 1
    assert handler.received == [envelope.message_id]
    assert (await client.xpending(stream, group))["pending"] == 0
    await client.flushdb()
    await client.aclose()
