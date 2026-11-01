from __future__ import annotations

from uuid import uuid4

from apyra.messaging import (
    DeliveryContext,
    ExponentialBackoff,
    InMemoryIdempotencyStore,
    MessageEnvelope,
)


def test_envelope_defaults() -> None:
    envelope = MessageEnvelope(payload={"hello": "world"})
    assert envelope.message_id is not None
    assert envelope.payload == {"hello": "world"}


def test_retry_backoff_bounds() -> None:
    policy = ExponentialBackoff(max_attempts=3, base_delay_seconds=0.1, jitter=False)
    assert policy.next_delay(1) == 0.1
    assert policy.next_delay(2) == 0.2


async def test_idempotency_store() -> None:
    store = InMemoryIdempotencyStore()
    message_id = uuid4()
    assert await store.is_processed(message_id) is False
    await store.mark_processed(message_id)
    assert await store.is_processed(message_id) is True


def test_delivery_context() -> None:
    context = DeliveryContext(message_id=uuid4(), attempt=1, consumer="worker")
    assert context.attempt == 1
