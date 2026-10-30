"""Redis Streams event bus for durable, multi-process events."""

from __future__ import annotations

import asyncio
import contextlib
import json
from collections import defaultdict
from collections.abc import Awaitable, Callable, Mapping
from datetime import UTC, datetime
from typing import Any, Protocol

from .events import Event

Handler = Callable[[Event], Awaitable[None] | None]


class RedisStreamClient(Protocol):
    async def xadd(
        self,
        name: str,
        fields: dict[str, str],
        *,
        maxlen: int | None = None,
        approximate: bool = True,
    ) -> str: ...

    async def xread(
        self, streams: dict[str, str], *, count: int | None = None, block: int | None = None
    ) -> list[Any] | None: ...

    async def aclose(self) -> None: ...


class RedisStreamEventBus:
    """Publish events to a Redis Stream and dispatch them to subscribers."""

    def __init__(
        self,
        client: RedisStreamClient,
        *,
        stream: str = "apyra:events",
        max_concurrency: int = 10,
        block_ms: int = 1000,
    ) -> None:
        self._client = client
        self._stream = stream
        self._handlers: dict[str, list[Handler]] = defaultdict(list)
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._block_ms = block_ms
        self._last_id = "$"
        self._reader: asyncio.Task[None] | None = None
        self._closed = False

    def subscribe(self, event_name: str, handler: Handler) -> None:
        self._handlers[event_name].append(handler)
        if self._reader is None or self._reader.done():
            self._reader = asyncio.create_task(self._read_loop())

    def unsubscribe(self, event_name: str, handler: Handler) -> None:
        handlers = self._handlers.get(event_name)
        if handlers is not None:
            self._handlers[event_name] = [item for item in handlers if item is not handler]

    async def publish(self, event: Event) -> list[BaseException]:
        fields = {
            "name": event.name,
            "payload": json.dumps(event.payload, separators=(",", ":")),
            "occurred_at": event.occurred_at.isoformat(),
        }
        await self._client.xadd(self._stream, fields)
        return []

    async def _read_loop(self) -> None:
        try:
            while not self._closed:
                response = await self._client.xread(
                    {self._stream: self._last_id}, count=100, block=self._block_ms
                )
                if response is None:
                    await asyncio.sleep(0)
                    continue
                for _stream_name, messages in response:
                    for message_id, fields in messages:
                        self._last_id = _decode_id(message_id)
                        event = _decode_event(fields)
                        if event is None:
                            continue
                        handlers = list(self._handlers.get(event.name, ()))
                        await self._dispatch(handlers, event)
        except asyncio.CancelledError:
            return

    async def _dispatch(self, handlers: list[Handler], event: Event) -> None:
        async def run(handler: Handler) -> None:
            async with self._semaphore:
                result = handler(event)
                if hasattr(result, "__await__"):
                    await result  # type: ignore[misc]

        results = await asyncio.gather(
            *(run(handler) for handler in handlers), return_exceptions=True
        )
        for result in results:
            if isinstance(result, BaseException):
                # Dispatch errors are intentionally not propagated from the reader.
                pass

    async def close(self) -> None:
        self._closed = True
        if self._reader is not None:
            self._reader.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self._reader
            self._reader = None
        await self._client.aclose()


def _decode_id(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return str(value)


def _decode_event(fields: Any) -> Event | None:
    if not isinstance(fields, Mapping):
        return None
    normalized = {
        (key.decode("utf-8") if isinstance(key, bytes) else str(key)): (
            value.decode("utf-8") if isinstance(value, bytes) else value
        )
        for key, value in fields.items()
    }
    name = normalized.get("name")
    if not isinstance(name, str):
        return None
    payload_raw = normalized.get("payload", "{}")
    try:
        payload = json.loads(payload_raw) if isinstance(payload_raw, str) else {}
    except json.JSONDecodeError:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    occurred_at = datetime.now(UTC)
    occurred_raw = normalized.get("occurred_at")
    if isinstance(occurred_raw, str):
        try:
            occurred_at = datetime.fromisoformat(occurred_raw)
        except ValueError:
            occurred_at = datetime.now(UTC)
    return Event(name=name, payload=payload, occurred_at=occurred_at)
