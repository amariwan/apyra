"""RabbitMQ event bus for durable, multi-process events."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from collections import defaultdict
from typing import Any, cast

_aio_pika: Any
try:  # pragma: no cover - exercised only when the optional dependency is installed
    import aio_pika as _aio_pika
except ImportError:  # pragma: no cover - optional dependency
    _aio_pika = None

aio_pika: Any = _aio_pika

from .dispatch import Handler, invoke_handler
from .events import Event, decode_occurred_at

logger: logging.Logger = logging.getLogger("apyra.events.rabbitmq")


class RabbitMQEventBus:
    """Publish durable events and dispatch matching messages from a RabbitMQ queue."""

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
        if max_concurrency < 1:
            raise ValueError("max_concurrency must be positive")
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
        """Register a handler and start the background queue consumer if needed."""
        if self._closed:
            raise RuntimeError("event bus is closed")
        self._handlers[event_name].append(handler)
        if self._consumer is None or self._consumer.done():
            self._consumer = asyncio.create_task(self._consume())

    def unsubscribe(self, event_name: str, handler: Handler) -> None:
        """Remove registrations of this exact handler for the event name."""
        handlers = self._handlers.get(event_name)
        if handlers is not None:
            self._handlers[event_name] = [item for item in handlers if item is not handler]

    async def publish(self, event: Event) -> list[BaseException]:
        """Persist an event to the durable exchange; handlers run asynchronously."""
        if self._closed:
            raise RuntimeError("event bus is closed")
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
            aio_pika.Message(
                body=body,
                content_type="application/json",
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            ),
            routing_key=event.name,
        )
        return []

    async def _consume(self) -> None:
        while not self._closed:
            try:
                await self._connect()
                async with self._queue.iterator() as queue_iter:
                    async for message in queue_iter:
                        try:
                            async with message.process(requeue=True):
                                event = _decode_event(message.body)
                                if event is None:
                                    continue
                                handlers = list(self._handlers.get(event.name, ()))
                                await self._dispatch(handlers, event)
                        except asyncio.CancelledError:
                            raise
                        except Exception:
                            logger.exception("RabbitMQ event dispatch failed; message requeued")
                            await asyncio.sleep(1)
            except asyncio.CancelledError:
                return
            except Exception:
                logger.exception("RabbitMQ consumer failed; retrying in one second")
                channel = self._channel
                self._channel = None
                self._exchange = None
                self._queue = None
                if channel is not None:
                    with contextlib.suppress(Exception):
                        await channel.close()
                if not self._closed:
                    await asyncio.sleep(1)

    async def _dispatch(self, handlers: list[Handler], event: Event) -> None:
        async def run(handler: Handler) -> None:
            async with self._semaphore:
                await invoke_handler(handler, event)

        async with asyncio.TaskGroup() as tasks:
            for handler in handlers:
                tasks.create_task(run(handler))

    async def close(self) -> None:
        """Stop the consumer and close its channel and connection."""
        if self._closed:
            return
        self._closed = True
        if self._consumer is not None:
            self._consumer.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self._consumer
            self._consumer = None
        channel = self._channel
        connection = self._connection
        self._channel = None
        self._connection = None
        try:
            if channel is not None:
                await channel.close()
        finally:
            if connection is not None:
                await connection.close()


def _decode_event(body: bytes) -> Event | None:

    try:
        data = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError):
        return None
    if not isinstance(data, dict):
        return None
    data = cast(dict[str, object], data)
    name = data.get("name")
    if not isinstance(name, str):
        return None
    payload = data.get("payload", {})
    if isinstance(payload, dict):
        payload = cast(dict[str, object], payload)
    else:
        payload = {}

    return Event(
        name=name, payload=payload, occurred_at=decode_occurred_at(data.get("occurred_at"))
    )
