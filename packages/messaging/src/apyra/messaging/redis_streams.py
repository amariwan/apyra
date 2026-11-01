"""Redis Streams transport adapter for Apyra messaging."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

logger: logging.Logger = logging.getLogger(__name__)

from .contracts import DeliveryContext, MessageEnvelope, MessageHandler


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
            },
        )


class RedisStreamsConsumer:
    """Consume messages from a Redis Stream consumer group."""

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
        self._running = False

    async def ensure_group(self) -> None:
        try:
            await self._client.xgroup_create(self._stream, self._group, id="0", mkstream=True)
        except Exception as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    async def recover_pending(self) -> None:
        """Claim stale pending messages for recovery."""
        try:
            await self._client.xautoclaim(
                self._stream,
                self._group,
                self._consumer_name,
                self._min_idle_ms,
                start_id="0-0",
                count=self._batch_size,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("redis streams recovery failed: %s", exc)

    async def run(self) -> None:
        self._running = True
        await self.ensure_group()
        while self._running:
            await self.recover_pending()
            try:
                response = await self._client.xreadgroup(
                    groupname=self._group,
                    consumername=self._consumer_name,
                    streams={self._stream: ">"},
                    count=self._batch_size,
                    block=self._block_ms,
                )
            except Exception:  # noqa: BLE001
                await asyncio.sleep(0.5)
                continue
            if not response:
                continue
            for _, messages in response:
                for message_id, fields in messages:
                    envelope = MessageEnvelope(
                        message_id=__import__("uuid").UUID(fields["message_id"]),
                        payload=json.loads(fields["payload"]),
                    )
                    context = DeliveryContext(
                        message_id=envelope.message_id,
                        attempt=1,
                        consumer=self._consumer_name,
                    )
                    if (
                        self._idempotency_store is not None
                        and await self._idempotency_store.is_processed(envelope.message_id)
                    ):
                        await self._client.xack(self._stream, self._group, message_id)
                        continue
                    try:
                        await self._handler.handle(envelope, context)
                        if self._idempotency_store is not None:
                            await self._idempotency_store.mark_processed(envelope.message_id)
                        await self._client.xack(self._stream, self._group, message_id)
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("redis streams handler failed: %s", exc)
                        # Leave unacknowledged for retry/recovery.
                        continue

    def stop(self) -> None:
        self._running = False
