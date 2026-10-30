"""RabbitMQ event bus for durable, multi-process events."""

from __future__ import annotations

import asyncio
import contextlib
import json
from collections import defaultdict
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

_aio_pika: Any
try:  # pragma: no cover - exercised only when the optional dependency is installed
    import aio_pika as _aio_pika
except ImportError:  # pragma: no cover - optional dependency
    _aio_pika = None

aio_pika: Any = _aio_pika

from .events import Event

Handler = Callable[[Event], Awaitable[None] | None]


class RabbitMQEventBus:
    """Publish events to a RabbitMQ topic exchange and dispatch them to subscribers."""

    def __init__(
        self,
        *,
        url: str | None = None,
        connection: Any = None,
        exchange_name: str = "apyra.events",
        queue_name: str | None = None,
        routing_key: str = "#",
        max_concurrency: int = 10,
    ) -> None:
        if aio_pika is None:  # pragma: no cover - optional dependency
            raise RuntimeError("RabbitMQ events require the 'aio-pika' package")
        self._url = url
        self._connection = connection
        self._exchange_name = exchange_name
        self._queue_name = queue_name or f"{exchange_name}.queue"
        self._routing_key = routing_key
        self._handlers: dict[str, list[Handler]] = defaultdict(list)
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._channel: Any = None
        self._exchange: Any = None
        self._queue: Any = None
        self._consumer: asyncio.Task[None] | None = None
        self._closed = False

    async def _connect(self) -> None:
        if self._connection is None:
            if self._url is None:
                raise RuntimeError("RabbitMQ URL is required")
            self._connection = await aio_pika.connect_robust(self._url)
        if self._channel is None:
            self._channel = await self._connection.channel()
            self._exchange = await self._channel.declare_exchange(
                self._exchange_name, aio_pika.ExchangeType.TOPIC, durable=True
            )
            self._queue = await self._channel.declare_queue(self._queue_name, durable=True)
            await self._queue.bind(self._exchange, routing_key=self._routing_key)

    def subscribe(self, event_name: str, handler: Handler) -> None:
        self._handlers[event_name].append(handler)
        if self._consumer is None or self._consumer.done():
            self._consumer = asyncio.create_task(self._consume())

    def unsubscribe(self, event_name: str, handler: Handler) -> None:
        handlers = self._handlers.get(event_name)
        if handlers is not None:
            self._handlers[event_name] = [item for item in handlers if item is not handler]

    async def publish(self, event: Event) -> list[BaseException]:
        await self._connect()
        body = json.dumps(
            {
                "name": event.name,
                "payload": event.payload,
                "occurred_at": event.occurred_at.isoformat(),
            },
            separators=(",", ":"),
        ).encode("utf-8")
        await self._exchange.publish(
            aio_pika.Message(body=body, content_type="application/json"),
            routing_key=event.name,
        )
        return []

    async def _consume(self) -> None:
        try:
            await self._connect()
            async with self._queue.iterator() as queue_iter:
                async for message in queue_iter:
                    async with message.process():
                        event = _decode_event(message.body)
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

        await asyncio.gather(*(run(handler) for handler in handlers), return_exceptions=True)

    async def close(self) -> None:
        if self._consumer is not None:
            self._consumer.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self._consumer
            self._consumer = None
        if self._channel is not None:
            await self._channel.close()
            self._channel = None
        if self._connection is not None:
            await self._connection.close()
            self._connection = None


def _decode_event(body: bytes) -> Event | None:

    try:
        data = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    name = data.get("name")
    if not isinstance(name, str):
        return None
    payload = data.get("payload", {})
    if not isinstance(payload, dict):
        payload = {}

    occurred_at = datetime.now(UTC)
    occurred_raw = data.get("occurred_at")
    if isinstance(occurred_raw, str):
        try:
            occurred_at = datetime.fromisoformat(occurred_raw)
        except ValueError:
            occurred_at = datetime.now(UTC)
    return Event(name=name, payload=payload, occurred_at=occurred_at)
