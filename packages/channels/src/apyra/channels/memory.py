"""Single-process channel layer for local development and tests."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Callable
from typing import Any, cast

_CLOSED = object()


def _put_latest(queue: asyncio.Queue[Any | object], value: Any | object) -> None:
    if queue.full():
        queue.get_nowait()
    queue.put_nowait(value)


class MemoryChannelSubscription:
    """Async message stream backed by one in-process subscriber queue."""

    def __init__(
        self, queue: asyncio.Queue[Any | object], close_callback: Callable[[], None]
    ) -> None:
        """Create a subscription for an already registered queue."""
        self._queue = queue
        self._close_callback = close_callback
        self._closed = False

    def __aiter__(self) -> MemoryChannelSubscription:
        """Return this subscription as its asynchronous iterator."""
        return self

    async def __anext__(self) -> Any:
        """Wait for a message, or stop iteration after the subscription closes."""
        value = await self._queue.get()
        if value is _CLOSED:
            raise StopAsyncIteration
        return cast(Any, value)

    async def close(self) -> None:
        """Unregister this subscriber and wake any waiting iterator."""
        if self._closed:
            return
        self._closed = True
        self._close_callback()
        _put_latest(self._queue, _CLOSED)


class MemoryChannelLayer:
    """Single-process pub/sub layer that drops the oldest queued message on overflow."""

    def __init__(self, *, queue_size: int = 100) -> None:
        """Create a layer with a bounded queue for each subscriber."""
        self._queue_size = queue_size
        self._subscribers: dict[str, set[asyncio.Queue[Any | object]]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def publish(self, channel: str, message: Any) -> int:
        """Send a message to current subscribers and return their count."""
        async with self._lock:
            queues = tuple(self._subscribers.get(channel, ()))
        for queue in queues:
            _put_latest(queue, message)
        return len(queues)

    async def subscribe(self, channel: str) -> MemoryChannelSubscription:
        """Register a subscriber and return its async message stream."""
        queue: asyncio.Queue[Any | object] = asyncio.Queue(maxsize=self._queue_size)
        async with self._lock:
            self._subscribers[channel].add(queue)

        def remove() -> None:
            subscribers = self._subscribers.get(channel)
            if subscribers is not None:
                subscribers.discard(queue)
                if not subscribers:
                    self._subscribers.pop(channel, None)

        return MemoryChannelSubscription(queue, remove)

    async def close(self) -> None:
        """Remove all subscribers and stop their message streams."""
        async with self._lock:
            queues = [queue for subscribers in self._subscribers.values() for queue in subscribers]
            self._subscribers.clear()
        for queue in queues:
            _put_latest(queue, _CLOSED)


__all__ = ["MemoryChannelLayer", "MemoryChannelSubscription"]
