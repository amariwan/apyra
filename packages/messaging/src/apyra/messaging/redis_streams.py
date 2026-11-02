"""Redis Streams transport adapter for Apyra messaging.

Delivery semantics: **at-least-once**. The consumer reads new messages through a
consumer group and recovers pending (unacknowledged) messages left behind by
crashed workers. Duplicate delivery is possible and must be tolerated by the
handler or guarded with an ``IdempotencyStore``.

Recovery uses ``XPENDING``/``XCLAIM`` rather than ``XAUTOCLAIM`` because the
delivery count and idle time of each pending message are required to implement
exponential backoff and dead-lettering. Every reclaimed message is processed
through the same path as a newly delivered message.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from .contracts import (
    DeadLetterPolicy,
    DeliveryContext,
    MessageEnvelope,
    MessageHandler,
    RetryPolicy,
)

logger = logging.getLogger(__name__)

#: Signature for a lightweight, dependency-free metrics hook: ``(name, delta)``.
MetricsCallback = Callable[[str, int], None]

_DEFAULT_MAX_ATTEMPTS = 5


def _decode(value: Any) -> str:
    """Normalize a Redis field value (bytes or str) to ``str``."""
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return str(value)


class RedisStreamsPublisher:
    """Publish message envelopes to a Redis Stream."""

    def __init__(self, client: Any, stream: str, max_size_bytes: int = 1_048_576) -> None:
        self._client = client
        self._stream = stream
        self._max_size_bytes = max_size_bytes

    async def publish(self, envelope: MessageEnvelope) -> None:
        payload = json.dumps(envelope.payload, default=str).encode("utf-8")
        if len(payload) > self._max_size_bytes:
            raise ValueError("message payload exceeds size limit")
        await self._client.xadd(
            self._stream,
            {
                "message_id": str(envelope.message_id),
                "payload": payload.decode("utf-8"),
                "occurred_at": envelope.occurred_at.isoformat(),
                "apyra_attempts": "1",
            },
        )


class RedisStreamsConsumer:
    """Consume messages from a Redis Stream consumer group.

    The consumer guarantees at-least-once delivery: a message is acknowledged only
    after the handler returns, and abandoned pending messages are recovered and
    re-processed. When ``retry_policy`` is provided, failed messages are retried
    with exponential backoff up to ``retry_policy.max_attempts`` and then sent to
    the dead-letter sink. Without a retry policy, failed messages are retried
    indefinitely (matching the historical behavior) and are never dropped.
    """

    def __init__(
        self,
        client: Any,
        stream: str,
        group: str,
        consumer_name: str,
        handler: MessageHandler,
        batch_size: int = 10,
        block_ms: int = 1000,
        idempotency_store: Any = None,
        min_idle_ms: int = 60_000,
        *,
        retry_policy: RetryPolicy | None = None,
        dead_letter_policy: DeadLetterPolicy | None = None,
        dead_letter_stream: str | None = None,
        recover_batch_size: int = 100,
        on_metric: MetricsCallback | None = None,
        stop_grace_seconds: float = 30.0,
    ) -> None:
        self._client = client
        self._stream = stream
        self._group = group
        self._consumer_name = consumer_name
        self._handler = handler
        self._batch_size = batch_size
        self._block_ms = block_ms
        self._idempotency_store = idempotency_store
        self._min_idle_ms = min_idle_ms
        self._retry_policy = retry_policy
        self._dead_letter_policy = dead_letter_policy
        self._dead_letter_stream = dead_letter_stream
        self._recover_batch_size = recover_batch_size
        self._on_metric = on_metric
        self._stop_grace_seconds = stop_grace_seconds
        self._running = False

    # -- lifecycle ---------------------------------------------------------

    async def ensure_group(self) -> None:
        """Create the consumer group if it does not exist yet."""
        try:
            await self._client.xgroup_create(self._stream, self._group, id="0", mkstream=True)
        except Exception as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    def stop(self) -> None:
        """Request a graceful shutdown.

        The consumer stops reading new messages after the current in-flight batch
        completes; the blocking read returns within ``block_ms`` at most.
        """
        self._running = False

    # -- processing --------------------------------------------------------

    def _supports_atomic_claim(self) -> bool:
        return callable(getattr(self._idempotency_store, "claim", None))

    async def _process(self, message_id: str, fields: Any, attempt: int) -> str:
        data = {key: _decode(value) for key, value in fields.items()}
        envelope = MessageEnvelope(
            message_id=UUID(data.get("message_id", message_id)),
            payload=json.loads(data["payload"]),
            occurred_at=datetime.fromisoformat(data["occurred_at"])
            if data.get("occurred_at")
            else datetime.now(UTC),
        )
        context = DeliveryContext(
            message_id=envelope.message_id,
            attempt=attempt,
            consumer=self._consumer_name,
        )

        store = self._idempotency_store
        claimed = False
        if store is not None:
            if self._supports_atomic_claim():
                outcome = await store.claim(envelope.message_id)
                if outcome == "already_done":
                    await self._client.xack(self._stream, self._group, message_id)
                    self._record_metric("duplicate", 1)
                    return "duplicate"
                if outcome == "in_progress":
                    # Another worker owns this message; leave it pending for retry.
                    self._record_metric("in_progress", 1)
                    return "in_progress"
                claimed = True
            elif await store.is_processed(envelope.message_id):
                await self._client.xack(self._stream, self._group, message_id)
                self._record_metric("duplicate", 1)
                return "duplicate"

        try:
            await self._handler.handle(envelope, context)
        except Exception as exc:  # noqa: BLE001 - handler failures are expected
            logger.warning(
                "message handler failed",
                extra={
                    "message_id": str(envelope.message_id),
                    "attempt": attempt,
                    "error": str(exc),
                },
            )
            self._record_metric("failed", 1)
            # Leave unacknowledged: recovery/redelivery will retry it.
            return "failed"

        if store is not None:
            if claimed:
                await store.complete(envelope.message_id)
            else:
                await store.mark_processed(envelope.message_id)
        await self._client.xack(self._stream, self._group, message_id)
        self._record_metric("processed", 1)
        return "acked"

    async def _dead_letter(self, message_id: str, fields: Any, reason: str) -> None:
        data = {key: _decode(value) for key, value in fields.items()}
        envelope = MessageEnvelope(
            message_id=UUID(data.get("message_id", message_id)),
            payload=json.loads(data["payload"]),
            occurred_at=datetime.fromisoformat(data["occurred_at"])
            if data.get("occurred_at")
            else datetime.now(UTC),
        )
        if self._dead_letter_policy is not None:
            await self._dead_letter_policy.dead_letter(envelope, reason)
        elif self._dead_letter_stream is not None:
            await self._client.xadd(
                self._dead_letter_stream,
                {
                    "message_id": data.get("message_id", message_id),
                    "payload": data.get("payload", "{}"),
                    "occurred_at": data.get("occurred_at", ""),
                    "apyra_error": reason,
                },
            )
        else:
            logger.error(
                "message exhausted retries and was dropped",
                extra={"message_id": data.get("message_id", message_id), "error": reason},
            )
        await self._client.xack(self._stream, self._group, message_id)
        if self._dead_letter_policy is not None or self._dead_letter_stream is not None:
            await self._client.xdel(self._stream, message_id)
        self._record_metric("dead_lettered", 1)

    def _required_idle_ms(self, delivery_count: int) -> float:
        if self._retry_policy is None:
            return float(self._min_idle_ms)
        delay = self._retry_policy.next_delay(delivery_count)
        return max(float(self._min_idle_ms), delay * 1000.0)

    # -- recovery ----------------------------------------------------------

    async def recover_pending(self) -> int:
        """Recover abandoned pending messages and process them.

        Returns the number of messages processed during this pass. The pass is
        bounded to ``recover_batch_size`` entries so a poison message cannot cause
        an unbounded recovery loop; the outer ``run`` loop repeats the pass.
        """
        max_attempts = self._retry_policy.max_attempts if self._retry_policy is not None else None
        pending = await self._client.xpending_range(
            self._stream, self._group, min="-", max="+", count=self._recover_batch_size
        )

        claimed_ids: list[str] = []
        attempts: dict[str, int] = {}
        for entry in pending:
            message_id = _decode(entry["message_id"])
            delivery_count = int(entry["times_delivered"])
            if max_attempts is not None and delivery_count >= max_attempts:
                # Exhausted: move to the dead-letter sink instead of retrying.
                fields = await self._fetch_fields(message_id)
                await self._dead_letter(message_id, fields, "max_attempts_exceeded")
                continue
            idle_ms = int(entry["time_since_delivered"])
            if idle_ms >= self._required_idle_ms(delivery_count):
                claimed_ids.append(message_id)
                # delivery_count increments on claim; this is the next attempt.
                attempts[message_id] = delivery_count + 1

        processed = 0
        if claimed_ids:
            claimed = await self._client.xclaim(
                self._stream,
                self._group,
                self._consumer_name,
                self._min_idle_ms,
                claimed_ids,
            )
            for message_id, fields in claimed:
                if fields is None:
                    # The entry was deleted between XPENDING and XCLAIM.
                    continue
                message_id_str = _decode(message_id)
                outcome = await self._process(
                    message_id_str, fields, attempts.get(message_id_str, 1)
                )
                if outcome == "acked":
                    self._record_metric("recovered", 1)
                processed += 1
        return processed

    async def _fetch_fields(self, message_id: str) -> Any:
        entries = await self._client.xrange(self._stream, min=message_id, max=message_id)
        if not entries:
            return {}
        return entries[0][1]

    # -- main loop ---------------------------------------------------------

    async def run(self) -> None:
        """Run the consume loop until :meth:`stop` is called."""
        self._running = True
        await self.ensure_group()
        while self._running:
            try:
                await self.recover_pending()
            except Exception as exc:  # noqa: BLE001 - recovery must not kill the loop
                logger.warning("recovery pass failed", extra={"error": str(exc)})

            try:
                response = await self._client.xreadgroup(
                    groupname=self._group,
                    consumername=self._consumer_name,
                    streams={self._stream: ">"},
                    count=self._batch_size,
                    block=self._block_ms,
                )
            except Exception as exc:  # noqa: BLE001 - transient Redis errors
                logger.warning("read failed; retrying", extra={"error": str(exc)})
                await asyncio.sleep(0.5)
                continue

            if not response:
                continue

            for _, messages in response:
                for message_id, fields in messages:
                    if not self._running:
                        return
                    await self._process(_decode(message_id), fields, attempt=1)

    def _record_metric(self, name: str, delta: int) -> None:
        if self._on_metric is not None:
            self._on_metric(name, delta)
