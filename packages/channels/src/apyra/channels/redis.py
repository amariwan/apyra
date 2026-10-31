"""Redis Pub/Sub channel layer for multi-process WebSocket fan-out."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from typing import Any, Protocol, cast

_CLOSED = object()
logger: logging.Logger = logging.getLogger("apyra.channels.redis")


class RedisPubSub(Protocol):
    """Subset of a Redis Pub/Sub handle needed by channel subscriptions."""

    async def subscribe(self, *channels: str) -> None:
        """Start receiving messages from the named Redis channels."""
        ...

    async def unsubscribe(self, *channels: str) -> None:
        """Stop receiving messages from the named Redis channels."""
        ...

    async def get_message(self, **options: object) -> dict[str, object] | None:
        """Return one pending Pub/Sub message, or ``None`` when none is ready."""
        ...

    async def aclose(self) -> None:
        """Release the Pub/Sub connection."""
        ...


class RedisClient(Protocol):
    """Subset of an async Redis client required by ``RedisChannelLayer``."""

    async def publish(self, channel: str, message: str) -> int:
        """Publish serialized text and return Redis's subscriber count."""
        ...

    def pubsub(self) -> RedisPubSub:
        """Create a Pub/Sub handle for an independent subscription."""
        ...

    async def aclose(self) -> None:
        """Close the Redis client and its connections."""
        ...


class RedisChannelSubscription:
    """Async Redis message stream; malformed JSON is delivered as its raw string."""

    def __init__(self, pubsub: RedisPubSub, channel: str, *, queue_size: int = 100) -> None:
        """Subscribe-reader wrapper; a full local queue drops its oldest message."""
        self._pubsub = pubsub
        self._channel = channel
        self._queue: asyncio.Queue[Any | object] = asyncio.Queue(maxsize=max(1, queue_size))
        self._closed = False
        self._reader = asyncio.create_task(self._read_messages())

    def _drop_oldest_and_put(self, value: Any) -> None:
        if self._queue.full():
            with contextlib.suppress(asyncio.QueueEmpty):
                self._queue.get_nowait()
        self._queue.put_nowait(value)

    async def _read_messages(self) -> None:
        try:
            while not self._closed:
                item = await self._pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if item is None:
                    await asyncio.sleep(0)
                    continue
                raw = item.get("data")
                if isinstance(raw, bytes):
                    raw = raw.decode("utf-8")
                if isinstance(raw, str):
                    try:
                        self._drop_oldest_and_put(json.loads(raw))
                    except json.JSONDecodeError:
                        self._drop_oldest_and_put(raw)
        except asyncio.CancelledError:
            return
        except Exception:
            if not self._closed:
                logger.exception("Redis channel subscription reader failed; closing stream")
                self._drop_oldest_and_put(_CLOSED)
        finally:
            with contextlib.suppress(asyncio.QueueFull):
                self._queue.put_nowait(_CLOSED)

    def __aiter__(self) -> RedisChannelSubscription:
        """Return this subscription as its asynchronous iterator."""
        return self

    async def __anext__(self) -> Any:
        """Wait for the next decoded message or stop after closure/reader failure."""
        if self._closed and self._queue.empty():
            raise StopAsyncIteration
        value = await self._queue.get()
        if value is _CLOSED:
            raise StopAsyncIteration
        return cast(Any, value)

    async def close(self) -> None:
        """Cancel the reader, unsubscribe, and close the Pub/Sub handle."""
        if self._closed:
            return
        self._closed = True
        self._reader.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await self._reader
        try:
            await self._pubsub.unsubscribe(self._channel)
        finally:
            await self._pubsub.aclose()


class RedisChannelLayer:
    """Redis Pub/Sub layer for cross-process fan-out using JSON messages."""

    def __init__(
        self, client: RedisClient, *, prefix: str = "app:channels", queue_size: int = 100
    ) -> None:
        """Create a layer that namespaces channel names and bounds subscriber queues."""
        self._client = client
        self._prefix = prefix.strip(":")
        self._queue_size = queue_size

    def _channel(self, channel: str) -> str:
        return f"{self._prefix}:{channel}" if self._prefix else channel

    async def publish(self, channel: str, message: Any) -> int:
        """JSON-encode and publish a message; return Redis's subscriber count."""
        return await self._client.publish(
            self._channel(channel), json.dumps(message, separators=(",", ":"))
        )

    async def subscribe(self, channel: str) -> RedisChannelSubscription:
        """Subscribe to a namespaced channel and return its async message stream."""
        namespaced_channel = self._channel(channel)
        pubsub = self._client.pubsub()
        try:
            await pubsub.subscribe(namespaced_channel)
        except BaseException:
            try:
                await pubsub.aclose()
            except Exception:
                logger.exception("Failed to close Redis Pub/Sub handle after subscribe failure")
            raise
        return RedisChannelSubscription(pubsub, namespaced_channel, queue_size=self._queue_size)

    async def close(self) -> None:
        """Close the shared Redis client and all associated connections."""
        await self._client.aclose()


__all__ = ["RedisChannelLayer", "RedisChannelSubscription"]
