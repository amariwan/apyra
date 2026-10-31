"""Redis Streams event bus for durable, multi-process events."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from collections import defaultdict
from collections.abc import Mapping
from typing import Any, Protocol, cast

from .dispatch import Handler, invoke_handler
from .events import Event, decode_occurred_at

logger: logging.Logger = logging.getLogger("apyra.events.redis")


class RedisStreamClient(Protocol):
    """Subset of an async Redis client used by the stream event bus."""

    async def xrevrange(self, name: str, *, count: int) -> list[tuple[Any, Any]] | None:
        """Read newest stream entries, used to establish the initial cursor."""
        ...

    async def xadd(
        self,
        name: str,
        fields: dict[str, str],
        *,
        maxlen: int | None = None,
        approximate: bool = True,
    ) -> str:
        """Append fields to a stream and return the new entry ID."""
        ...

    async def xread(
        self, streams: dict[str, str], *, count: int | None = None, block: int | None = None
    ) -> list[Any] | None:
        """Read stream entries after each supplied cursor, optionally blocking."""
        ...

    async def aclose(self) -> None:
        """Close the Redis client and its connections."""
        ...


class RedisStreamEventBus:
    """Publish durable events and read new Redis Stream entries for subscribers."""

    def __init__(
        self,
        client: RedisStreamClient,
        *,
        stream: str = "apyra:events",
        max_concurrency: int = 10,
        block_ms: int = 1000,
    ) -> None:
        if max_concurrency < 1:
            raise ValueError("max_concurrency must be positive")
        self._client = client
        self._stream = stream
        self._handlers: dict[str, list[Handler]] = defaultdict(list)
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._block_ms = block_ms
        self._last_id = "$"
        self._reader: asyncio.Task[None] | None = None
        self._reader_ready = asyncio.Event()
        self._closed = False
        self._client_closed = False
        self._close_lock = asyncio.Lock()

    def subscribe(self, event_name: str, handler: Handler) -> None:
        """Register a handler and start the stream reader if needed."""
        if self._closed:
            raise RuntimeError("event bus is closed")
        self._handlers[event_name].append(handler)
        if self._reader is None or self._reader.done():
            self._reader_ready.clear()
            self._reader = asyncio.create_task(self._read_loop())

    def unsubscribe(self, event_name: str, handler: Handler) -> None:
        """Remove registrations of this exact handler for the event name."""
        handlers = self._handlers.get(event_name)
        if handlers is not None:
            self._handlers[event_name] = [item for item in handlers if item is not handler]

    async def publish(self, event: Event) -> list[BaseException]:
        """Append an event to the stream; dispatch happens in the reader task."""
        if self._closed:
            raise RuntimeError("event bus is closed")
        if self._reader is not None and not self._reader.done():
            await self._reader_ready.wait()
            if self._closed:
                raise RuntimeError("event bus is closed")
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
                try:
                    if self._last_id == "$":
                        # Resolve the initial cursor once; repeating "$" can skip entries.
                        latest = await self._client.xrevrange(self._stream, count=1)
                        self._last_id = (
                            _decode_id(latest[0][0])
                            if latest and latest[0][0] is not None
                            else "0-0"
                        )
                    self._reader_ready.set()
                    response = await self._client.xread(
                        {self._stream: self._last_id}, count=100, block=self._block_ms
                    )
                except Exception:
                    logger.exception("Redis event reader failed; retrying in one second")
                    await asyncio.sleep(1)
                    continue
                if response is None:
                    await asyncio.sleep(0)
                    continue
                for _stream_name, messages in response:
                    for message_id, fields in messages:
                        decoded_id = _decode_id(message_id)
                        event = _decode_event(fields)
                        if event is None:
                            self._last_id = decoded_id
                            continue
                        handlers = list(self._handlers.get(event.name, ()))
                        while True:
                            try:
                                await self._dispatch(handlers, event)
                            except Exception:
                                logger.exception(
                                    "Redis event dispatch failed; retrying event %s", event.name
                                )
                                await asyncio.sleep(1)
                                continue
                            break
                        self._last_id = decoded_id
        except asyncio.CancelledError:
            return

    async def _dispatch(self, handlers: list[Handler], event: Event) -> None:
        async def run(handler: Handler) -> None:
            async with self._semaphore:
                await invoke_handler(handler, event)

        async with asyncio.TaskGroup() as tasks:
            for handler in handlers:
                tasks.create_task(run(handler))

    async def close(self) -> None:
        """Stop the background reader and close the Redis client."""
        async with self._close_lock:
            if not self._closed:
                self._closed = True
                self._reader_ready.set()
                if self._reader is not None:
                    self._reader.cancel()
                    with contextlib.suppress(asyncio.CancelledError, Exception):
                        await self._reader
                    self._reader = None
            if not self._client_closed:
                await self._client.aclose()
                self._client_closed = True


def _decode_id(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return str(value)


def _decode_event(fields: Any) -> Event | None:
    if not isinstance(fields, Mapping):
        return None
    try:
        normalized: dict[str, object] = {}
        for key, value in cast(Mapping[object, object], fields).items():
            field_name = key.decode("utf-8") if isinstance(key, bytes) else str(key)
            normalized[field_name] = value.decode("utf-8") if isinstance(value, bytes) else value
    except UnicodeDecodeError:
        return None
    event_name = normalized.get("name")
    if not isinstance(event_name, str):
        return None
    payload_raw: object = normalized.get("payload", "{}")
    try:
        payload: object = json.loads(payload_raw) if isinstance(payload_raw, str) else {}
    except (json.JSONDecodeError, RecursionError):
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    else:
        payload = cast(dict[str, object], payload)
    return Event(
        name=event_name,
        payload=payload,
        occurred_at=decode_occurred_at(normalized.get("occurred_at")),
    )
