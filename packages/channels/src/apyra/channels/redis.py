"""Redis Pub/Sub channel layer for multi-process WebSocket fan-out."""

from __future__ import annotations

import asyncio
import contextlib
import json
from typing import Any, Protocol, cast

_CLOSED = object()


class RedisPubSub(Protocol):
    async def subscribe(self, *channels: str) -> None: ...

    async def unsubscribe(self, *channels: str) -> None: ...

    async def get_message(self, **options: object) -> dict[str, object] | None: ...

    async def aclose(self) -> None: ...


class RedisClient(Protocol):
    async def publish(self, channel: str, message: str) -> int: ...

    def pubsub(self) -> RedisPubSub: ...

    async def aclose(self) -> None: ...


class RedisChannelSubscription:
    def __init__(self, pubsub: RedisPubSub, channel: str, *, queue_size: int = 100) -> None:
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
        except (RuntimeError, ValueError, OSError):
            if not self._closed:
                self._drop_oldest_and_put(_CLOSED)
        finally:
            with contextlib.suppress(asyncio.QueueFull):
                self._queue.put_nowait(_CLOSED)

    def __aiter__(self) -> RedisChannelSubscription:
        return self

    async def __anext__(self) -> Any:
        value = await self._queue.get()
        if value is _CLOSED:
            raise StopAsyncIteration
        return cast(Any, value)

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._reader.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await self._reader
        await self._pubsub.unsubscribe(self._channel)
        await self._pubsub.aclose()


class RedisChannelLayer:
    def __init__(
        self, client: RedisClient, *, prefix: str = "app:channels", queue_size: int = 100
    ) -> None:
        self._client = client
        self._prefix = prefix.strip(":")
        self._queue_size = queue_size

    def _channel(self, channel: str) -> str:
        return f"{self._prefix}:{channel}" if self._prefix else channel

    async def publish(self, channel: str, message: Any) -> int:
        return await self._client.publish(
            self._channel(channel), json.dumps(message, separators=(",", ":"))
        )

    async def subscribe(self, channel: str) -> RedisChannelSubscription:
        namespaced_channel = self._channel(channel)
        pubsub = self._client.pubsub()
        await pubsub.subscribe(namespaced_channel)
        return RedisChannelSubscription(pubsub, namespaced_channel, queue_size=self._queue_size)

    async def close(self) -> None:
        await self._client.aclose()


__all__ = ["RedisChannelLayer", "RedisChannelSubscription"]
