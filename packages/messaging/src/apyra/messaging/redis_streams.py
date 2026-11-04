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
from typing import Any, cast
from uuid import NAMESPACE_URL, UUID, uuid5

from .contracts import (
    DeadLetterPolicy,
    DeliveryContext,
    MessageEnvelope,
    MessageHandler,
    RetryPolicy,
)

logger: logging.Logger = logging.getLogger(__name__)

#: Signature for a lightweight, dependency-free metrics hook: ``(name, delta)``.
MetricsCallback = Callable[[str, int], None]

_DEFAULT_MAX_ATTEMPTS = 5
_ATTEMPT_TTL_SECONDS = 604_800
_RECORD_ATTEMPT_SCRIPT = """
local attempts = redis.call('INCR', KEYS[1])
redis.call('EXPIRE', KEYS[1], ARGV[1])
return attempts
"""


def _decode(value: Any, *, errors: str = "strict") -> str:
    """Normalize a Redis field value (bytes or str) to ``str``."""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors=errors)
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
    indefinitely (matching the historical behavior) and are never dropped. If a
    dead-letter sink is not configured, exhausted and malformed entries remain
    pending for operator recovery instead of being acknowledged and lost.
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
        self._recovery_cursor = "-"
        self._recovery_cycle_max: str | None = None
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

    def _attempt_key(self, stream_entry_id: str) -> str:
        return f"apyra:messaging:attempts:{self._group}:{self._stream}:{stream_entry_id}"

    async def _attempt_count(self, stream_entry_id: str) -> int:
        value = await self._client.get(self._attempt_key(stream_entry_id))
        return int(value) if value is not None else 0

    async def _record_attempt(self, stream_entry_id: str) -> int:
        result = await self._client.eval(
            _RECORD_ATTEMPT_SCRIPT,
            1,
            self._attempt_key(stream_entry_id),
            str(_ATTEMPT_TTL_SECONDS),
        )
        return int(result)

    async def _clear_attempts(self, stream_entry_id: str) -> None:
        await self._client.delete(self._attempt_key(stream_entry_id))

    async def _release_claim(self, store: Any, message_id: UUID) -> None:
        release_claim = getattr(store, "release", None)
        if not callable(release_claim):
            return
        try:
            await cast(Any, release_claim)(message_id)
        except Exception as release_error:  # noqa: BLE001
            logger.warning(
                "failed to release message idempotency claim",
                extra={"message_id": str(message_id), "error_type": type(release_error).__name__},
            )

    def _create_envelope(self, message_id: str, fields: Any) -> MessageEnvelope:
        data = {key: _decode(value) for key, value in fields.items()}
        return MessageEnvelope(
            message_id=UUID(data.get("message_id", message_id)),
            payload=json.loads(data["payload"]),
            occurred_at=datetime.fromisoformat(data["occurred_at"])
            if data.get("occurred_at")
            else datetime.now(UTC),
        )

    async def _process(self, message_id: str, fields: Any, attempt: int) -> str:
        try:
            envelope = self._create_envelope(message_id, fields)
        except (KeyError, TypeError, ValueError) as exc:
            logger.error(
                "invalid message payload; applying the configured dead-letter behavior",
                extra={"message_id": message_id, "error_type": type(exc).__name__},
            )
            self._record_metric("invalid", 1)
            dead_lettered = await self._dead_letter(message_id, fields, "invalid_message_payload")
            return "invalid" if dead_lettered else "deferred"

        store = self._idempotency_store
        claimed = False
        if store is not None:
            if self._supports_atomic_claim():
                outcome = await store.claim(envelope.message_id)
                if outcome == "already_done":
                    await self._client.xack(self._stream, self._group, message_id)
                    await self._clear_attempts(message_id)
                    self._record_metric("duplicate", 1)
                    return "duplicate"
                if outcome == "in_progress":
                    # Keep this entry pending: recovery may have reclaimed the only
                    # delivery after its previous owner crashed before completion.
                    self._record_metric("in_progress", 1)
                    return "in_progress"
                claimed = True
            elif await store.is_processed(envelope.message_id):
                await self._client.xack(self._stream, self._group, message_id)
                await self._clear_attempts(message_id)
                self._record_metric("duplicate", 1)
                return "duplicate"

        try:
            attempt = await self._record_attempt(message_id)
        except asyncio.CancelledError:
            if claimed:
                await self._release_claim(store, envelope.message_id)
            raise
        except Exception as exc:  # noqa: BLE001 - keep the unacknowledged entry recoverable
            logger.warning(
                "could not record message attempt",
                extra={"message_id": message_id, "error_type": type(exc).__name__},
            )
            if claimed:
                await self._release_claim(store, envelope.message_id)
            return "deferred"
        context = DeliveryContext(
            message_id=envelope.message_id,
            attempt=attempt,
            consumer=self._consumer_name,
        )

        try:
            await self._handler.handle(envelope, context)
        except asyncio.CancelledError:
            if claimed:
                await self._release_claim(store, envelope.message_id)
            raise
        except Exception as exc:  # noqa: BLE001 - handler failures are expected
            logger.warning(
                "message handler failed",
                extra={
                    "message_id": str(envelope.message_id),
                    "attempt": attempt,
                    "error_type": type(exc).__name__,
                },
            )
            self._record_metric("failed", 1)
            if claimed:
                await self._release_claim(store, envelope.message_id)
            # Leave unacknowledged: recovery/redelivery will retry it.
            return "failed"

        if store is not None:
            if claimed:
                await store.complete(envelope.message_id)
            else:
                await store.mark_processed(envelope.message_id)
        await self._client.xack(self._stream, self._group, message_id)
        await self._clear_attempts(message_id)
        self._record_metric("processed", 1)
        return "acked"

    async def _dead_letter(
        self,
        message_id: str,
        fields: Any,
        reason: str,
        *,
        claimed_envelope: MessageEnvelope | None = None,
    ) -> bool:
        data = {
            _decode(key, errors="replace"): _decode(value, errors="replace")
            for key, value in fields.items()
        }
        try:
            envelope = self._create_envelope(message_id, fields)
        except (KeyError, TypeError, ValueError) as exc:
            logger.error(
                "invalid message could not be sent to the dead-letter policy",
                extra={"message_id": message_id, "error_type": type(exc).__name__},
            )
            if self._dead_letter_policy is not None:
                raw_fields = {
                    _decode(key, errors="replace"): _decode(value, errors="replace")
                    for key, value in fields.items()
                }
                invalid_envelope = MessageEnvelope(
                    message_id=uuid5(NAMESPACE_URL, f"{self._stream}:{message_id}"),
                    payload={"raw_fields": raw_fields},
                )
                await self._dead_letter_policy.dead_letter(invalid_envelope, reason)
            elif self._dead_letter_stream is not None:
                await self._client.xadd(
                    self._dead_letter_stream,
                    {
                        **data,
                        "apyra_error": reason,
                        "apyra_decode_error": type(exc).__name__,
                    },
                )
            else:
                logger.error(
                    "invalid message has no configured dead-letter sink",
                    extra={"message_id": message_id},
                )
                return False
            await self._client.xack(self._stream, self._group, message_id)
            await self._clear_attempts(message_id)
            self._record_metric("dead_lettered", 1)
            return True
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
                "message exhausted retries but remains pending without a dead-letter sink",
                extra={"message_id": data.get("message_id", message_id), "error": reason},
            )
            return False
        if claimed_envelope is not None and self._idempotency_store is not None:
            await self._idempotency_store.complete(claimed_envelope.message_id)
        await self._client.xack(self._stream, self._group, message_id)
        await self._clear_attempts(message_id)
        self._record_metric("dead_lettered", 1)
        return True

    def _required_idle_ms(self, delivery_count: int) -> float:
        if self._retry_policy is None:
            return float(self._min_idle_ms)
        delay = self._retry_policy.next_delay(delivery_count)
        return max(float(self._min_idle_ms), delay * 1000.0)

    # -- recovery ----------------------------------------------------------

    async def recover_pending(self) -> int:
        """Recover abandoned pending messages and process them.

        Returns the number of messages processed during this pass. Each call scans
        at most one page; a persistent cursor gives later pending entries a chance
        without allowing a growing pending list to starve normal reads.
        """
        max_attempts = self._retry_policy.max_attempts if self._retry_policy is not None else None
        claimed_ids: list[str] = []
        exhausted_ids: set[str] = set()
        if self._recovery_cycle_max is None:
            summary = await self._client.xpending(self._stream, self._group)
            cycle_max = summary.get("max") if summary else None
            if cycle_max is None:
                self._recovery_cursor = "-"
                return 0
            self._recovery_cycle_max = _decode(cycle_max)
        pending = await self._client.xpending_range(
            self._stream,
            self._group,
            min=self._recovery_cursor,
            max=self._recovery_cycle_max,
            count=self._recover_batch_size,
        )
        if not pending:
            self._recovery_cursor = "-"
            self._recovery_cycle_max = None
        for entry in pending:
            message_id = _decode(entry["message_id"])
            self._recovery_cursor = f"({message_id}"
            attempt_count = await self._attempt_count(message_id)
            idle_ms = int(entry["time_since_delivered"])
            if idle_ms >= self._required_idle_ms(max(attempt_count, 1)):
                claimed_ids.append(message_id)
                if max_attempts is not None and attempt_count >= max_attempts:
                    exhausted_ids.add(message_id)
        if len(pending) < self._recover_batch_size:
            self._recovery_cursor = "-"
            self._recovery_cycle_max = None

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
                if message_id_str in exhausted_ids:
                    envelope: MessageEnvelope | None = None
                    store = self._idempotency_store
                    try:
                        envelope = self._create_envelope(message_id_str, fields)
                    except (KeyError, TypeError, ValueError):
                        pass
                    if store is not None and envelope is not None:
                        if self._supports_atomic_claim():
                            claim = await store.claim(envelope.message_id)
                            if claim == "already_done":
                                await self._client.xack(self._stream, self._group, message_id_str)
                                await self._clear_attempts(message_id_str)
                                self._record_metric("duplicate", 1)
                                processed += 1
                                continue
                            if claim == "in_progress":
                                self._record_metric("in_progress", 1)
                                processed += 1
                                continue
                            try:
                                dead_lettered = await self._dead_letter(
                                    message_id_str,
                                    fields,
                                    "max_attempts_exceeded",
                                    claimed_envelope=envelope,
                                )
                                if not dead_lettered:
                                    await self._release_claim(store, envelope.message_id)
                            except BaseException:
                                await self._release_claim(store, envelope.message_id)
                                raise
                        elif await store.is_processed(envelope.message_id):
                            await self._client.xack(self._stream, self._group, message_id_str)
                            await self._clear_attempts(message_id_str)
                            self._record_metric("duplicate", 1)
                            processed += 1
                            continue
                        else:
                            await self._dead_letter(message_id_str, fields, "max_attempts_exceeded")
                    else:
                        await self._dead_letter(message_id_str, fields, "max_attempts_exceeded")
                    processed += 1
                    continue
                outcome = await self._process(message_id_str, fields, attempt=1)
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
                logger.warning("recovery pass failed", extra={"error_type": type(exc).__name__})

            try:
                response = await self._client.xreadgroup(
                    groupname=self._group,
                    consumername=self._consumer_name,
                    streams={self._stream: ">"},
                    count=self._batch_size,
                    block=self._block_ms,
                )
            except Exception as exc:  # noqa: BLE001 - transient Redis errors
                logger.warning("read failed; retrying", extra={"error_type": type(exc).__name__})
                await asyncio.sleep(0.5)
                try:
                    await self.ensure_group()
                except Exception as group_error:  # noqa: BLE001
                    logger.warning(
                        "consumer group recovery failed",
                        extra={"error_type": type(group_error).__name__},
                    )
                continue

            if not response:
                continue

            for _, messages in response:
                for message_id, fields in messages:
                    if not self._running:
                        return
                    decoded_message_id = _decode(message_id)
                    try:
                        await self._process(decoded_message_id, fields, attempt=1)
                    except asyncio.CancelledError:
                        raise
                    except Exception as exc:  # noqa: BLE001 - isolate failures per delivery
                        logger.error(
                            "message processing raised",
                            extra={
                                "message_id": decoded_message_id,
                                "error_type": type(exc).__name__,
                            },
                        )

    def _record_metric(self, name: str, delta: int) -> None:
        if self._on_metric is not None:
            self._on_metric(name, delta)
