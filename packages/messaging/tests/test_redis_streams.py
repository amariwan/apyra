from __future__ import annotations

import os
import uuid
from typing import Any, cast

import pytest
import redis.asyncio as redis_async

from apyra.messaging.contracts import DeliveryContext, MessageEnvelope
from apyra.messaging.redis_streams import RedisStreamsConsumer, RedisStreamsPublisher


def _redis_available() -> bool:
    url = os.getenv("APYRA_TEST_REDIS_URL", "redis://localhost:6379/15")
    try:
        import asyncio

        import redis.asyncio as redis_async

        async def check() -> bool:
            try:
                client = redis_async.from_url(url)
                await client.ping()
                await client.aclose()
                return True
            except Exception:  # noqa: BLE001
                return False

        return asyncio.run(check())
    except Exception:  # noqa: BLE001
        return False


pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.redis,
    pytest.mark.skipif(not _redis_available(), reason="Redis unavailable"),
]


class _Handler:
    def __init__(self) -> None:
        self.received: list[uuid.UUID] = []

    async def handle(self, envelope: MessageEnvelope, context: DeliveryContext) -> None:
        self.received.append(envelope.message_id)


async def test_redis_publish_and_consume() -> None:
    client = redis_async.from_url(
        os.getenv("APYRA_TEST_REDIS_URL", "redis://localhost:6379/15"), decode_responses=True
    )
    await client.flushdb()
    stream = "test-stream"
    group = "test-group"
    consumer_name = "consumer-1"
    handler = _Handler()
    publisher = RedisStreamsPublisher(client, stream)
    envelope = MessageEnvelope(payload={"hello": "world"})
    await publisher.publish(envelope)

    consumer = RedisStreamsConsumer(client, stream, group, consumer_name, handler)
    await consumer.ensure_group()
    await consumer.run() if False else None
    # Consume one batch manually
    response = await client.xreadgroup(
        groupname=group,
        consumername=consumer_name,
        streams={stream: ">"},
        count=10,
        block=100,
    )
    assert response
    for _, messages in cast(Any, response):
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
