from __future__ import annotations

import asyncio
import json
import subprocess
import sys
import threading
import warnings
from collections.abc import Callable
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Self, cast

import pytest

from apyra.events import Event, EventBus, InMemoryEventBus
from apyra.events.dispatch import invoke_handler
from apyra.events.rabbitmq import RabbitMQEventBus, _decode_event
from apyra.events.redis_streams import RedisStreamEventBus
from apyra.events.redis_streams import _decode_event as _decode_redis_event


@pytest.mark.asyncio
async def test_event_bus_base_methods_raise_when_called() -> None:
    bus = EventBus()

    with pytest.raises(NotImplementedError, match="publish"):
        await bus.publish(Event(name="test"))
    with pytest.raises(NotImplementedError, match="subscribe"):
        bus.subscribe("test", lambda _event: None)


def test_incomplete_event_bus_subclass_warns_and_remains_instantiable() -> None:
    with pytest.warns(DeprecationWarning, match="subscribe.*next major") as captured:

        class IncompleteEventBus(EventBus):
            async def publish(self, event: Event) -> list[BaseException]:
                return []

    assert len(captured) == 1
    assert captured[0].filename == __file__
    bus = IncompleteEventBus()
    with pytest.raises(NotImplementedError, match="subscribe"):
        bus.subscribe("test", lambda _event: None)


def test_event_bus_subclass_missing_publish_warns() -> None:
    with pytest.warns(DeprecationWarning, match="publish.*next major"):

        class IncompleteEventBus(EventBus):
            def subscribe(self, event_name: str, handler: Callable[[Event], object]) -> None:
                pass


def test_complete_event_bus_subclass_does_not_warn() -> None:
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")

        class CompleteEventBus(EventBus):
            async def publish(self, event: Event) -> list[BaseException]:
                return []

            def subscribe(self, event_name: str, handler: Callable[[Event], object]) -> None:
                pass

    assert captured == []


def test_builtin_event_bus_adapters_import_without_deprecation_warnings() -> None:
    result = subprocess.run(
        [sys.executable, "-W", "always::DeprecationWarning", "-c", "import apyra.events"],
        capture_output=True,
        check=True,
        text=True,
    )

    assert "DeprecationWarning" not in result.stderr


def test_in_memory_event_bus_requires_positive_concurrency() -> None:
    with pytest.raises(ValueError, match="max_concurrency must be positive"):
        InMemoryEventBus(max_concurrency=0)


def test_redis_stream_event_bus_requires_positive_concurrency() -> None:
    with pytest.raises(ValueError, match="max_concurrency must be positive"):
        RedisStreamEventBus(object(), max_concurrency=0)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_redis_publish_waits_for_subscriber_cursor_initialization() -> None:
    class StartupRaceClient:
        def __init__(self) -> None:
            self.cursor_started = asyncio.Event()
            self.release_cursor = asyncio.Event()
            self.event_added = asyncio.Event()
            self.appended = False

        async def xrevrange(self, _name: str, *, count: int) -> list[tuple[str, dict[str, str]]]:
            assert count == 1
            self.cursor_started.set()
            await self.release_cursor.wait()
            return []

        async def xadd(self, _name: str, _fields: dict[str, str], **_kwargs: object) -> str:
            self.appended = True
            self.event_added.set()
            return "1-0"

        async def xread(self, _streams: dict[str, str], **_kwargs: object) -> list[object]:
            await self.event_added.wait()
            fields = {"name": "created", "payload": "{}"}
            return [("events", [("1-0", fields)])]

        async def aclose(self) -> None:
            return None

    client = StartupRaceClient()
    bus = RedisStreamEventBus(client)  # type: ignore[arg-type]
    handled = asyncio.Event()

    async def handler(_event: Event) -> None:
        handled.set()

    bus.subscribe("created", handler)
    publish_task = asyncio.create_task(bus.publish(Event(name="created", payload={})))
    await client.cursor_started.wait()
    await asyncio.sleep(0)

    assert not client.appended

    client.release_cursor.set()
    await publish_task
    await asyncio.wait_for(handled.wait(), timeout=1)
    await bus.close()


def test_rabbitmq_event_bus_requires_positive_concurrency(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("apyra.events.rabbitmq.aio_pika", object())
    with pytest.raises(ValueError, match="max_concurrency must be positive"):
        RabbitMQEventBus(connection=object(), max_concurrency=0)


@pytest.mark.asyncio
async def test_rabbitmq_connect_requires_url_without_injected_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("apyra.events.rabbitmq.aio_pika", object())
    bus = RabbitMQEventBus()

    with pytest.raises(RuntimeError, match="RabbitMQ URL is required"):
        await bus._connect()


@pytest.mark.asyncio
async def test_rabbitmq_publish_connects_and_sends_durable_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, object] = {}
    channel_count = 0

    class Message:
        def __init__(self, *, body: bytes, content_type: str, delivery_mode: object) -> None:
            self.body = body
            self.content_type = content_type
            self.delivery_mode = delivery_mode

    class Exchange:
        async def publish(self, message: Message, *, routing_key: str) -> None:
            calls["message"] = message
            calls["routing_key"] = routing_key

    class Queue:
        async def bind(self, exchange: Exchange, *, routing_key: str) -> None:
            calls["binding"] = (exchange, routing_key)

    class Channel:
        async def declare_exchange(
            self, name: str, exchange_type: object, *, durable: bool
        ) -> Exchange:
            calls["exchange_declaration"] = (name, exchange_type, durable)
            return Exchange()

        async def declare_queue(self, name: str, *, durable: bool) -> Queue:
            calls["queue_declaration"] = (name, durable)
            return Queue()

    class Connection:
        async def channel(self) -> Channel:
            nonlocal channel_count
            channel_count += 1
            return Channel()

    async def connect_robust(url: str) -> Connection:
        calls["url"] = url
        return Connection()

    aio_pika_stub = SimpleNamespace(
        ExchangeType=SimpleNamespace(TOPIC="topic"),
        DeliveryMode=SimpleNamespace(PERSISTENT="persistent"),
        Message=Message,
        connect_robust=connect_robust,
    )
    monkeypatch.setattr("apyra.events.rabbitmq.aio_pika", aio_pika_stub)
    bus = RabbitMQEventBus(
        url="amqp://broker.example/vhost",
        exchange_name="domain.events",
        queue_name="worker-1",
        routing_key="orders.*",
    )
    occurred_at = datetime(2026, 10, 31, tzinfo=UTC)
    event = Event(name="orders.created", payload={"id": 7}, occurred_at=occurred_at)

    assert await bus.publish(event) == []
    assert await bus.publish(event) == []

    message = cast(Message, calls["message"])
    assert calls["url"] == "amqp://broker.example/vhost"
    assert calls["exchange_declaration"] == ("domain.events", "topic", True)
    assert calls["queue_declaration"] == ("worker-1", True)
    assert calls["binding"] == (bus._exchange, "orders.*")
    assert channel_count == 1
    assert message.content_type == "application/json"
    assert message.delivery_mode == "persistent"
    assert json.loads(message.body) == {
        "name": "orders.created",
        "payload": {"id": 7},
        "occurred_at": occurred_at.isoformat(),
    }
    assert calls["routing_key"] == "orders.created"


@pytest.mark.asyncio
async def test_rabbitmq_subscribe_unsubscribe_and_close_consumer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("apyra.events.rabbitmq.aio_pika", object())
    bus = RabbitMQEventBus()
    started = asyncio.Event()

    async def consume() -> None:
        started.set()
        await asyncio.Event().wait()

    async def first(_event: Event) -> None:
        return None

    async def second(_event: Event) -> None:
        return None

    monkeypatch.setattr(bus, "_consume", consume)
    bus.subscribe("created", first)
    consumer = bus._consumer
    bus.subscribe("created", second)
    bus.unsubscribe("created", first)
    bus.unsubscribe("missing", first)

    await started.wait()
    assert bus._handlers["created"] == [second]
    assert bus._consumer is consumer
    await bus.close()

    assert bus._consumer is None
    assert consumer is not None and consumer.done()


@pytest.mark.asyncio
async def test_rabbitmq_closed_bus_rejects_operations_and_close_is_idempotent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("apyra.events.rabbitmq.aio_pika", object())

    class Connection:
        close_calls = 0

        async def close(self) -> None:
            self.close_calls += 1

    connection = Connection()
    bus = RabbitMQEventBus(connection=connection)
    await bus.close()
    await bus.close()

    assert connection.close_calls == 1
    with pytest.raises(RuntimeError, match="event bus is closed"):
        bus.subscribe("created", lambda _event: None)
    with pytest.raises(RuntimeError, match="event bus is closed"):
        await bus.publish(Event(name="created", payload={}))


@pytest.mark.parametrize(
    "body",
    [b"\xff", b"{", b"[]", b'{"name": 42}'],
)
def test_decode_event_rejects_malformed_body_or_name(body: bytes) -> None:
    assert _decode_event(body) is None


def test_decode_event_rejects_deeply_nested_json() -> None:
    body = b'{"name":"created","payload":' + b"[" * 10000 + b"0" + b"]" * 10000 + b"}"

    assert _decode_event(body) is None


def test_decode_event_defaults_invalid_payload_and_timestamp() -> None:
    event = _decode_event(b'{"name":"created","payload":[],"occurred_at":"invalid"}')

    assert event is not None
    assert event.name == "created"
    assert event.payload == {}
    assert event.occurred_at.tzinfo == UTC


def test_event_decoders_default_naive_timestamps_to_utc() -> None:
    rabbit_event = _decode_event(b'{"name":"created","occurred_at":"2026-10-31T12:00:00"}')
    redis_event = _decode_redis_event({"name": "created", "occurred_at": "2026-10-31T12:00:00"})

    assert rabbit_event is not None and rabbit_event.occurred_at.tzinfo == UTC
    assert redis_event is not None and redis_event.occurred_at.tzinfo == UTC


@pytest.mark.asyncio
async def test_event_bus_calls_handlers() -> None:
    bus = InMemoryEventBus()
    seen: list[str] = []

    async def handler(event: Event) -> None:
        seen.append(str(event.payload["value"]))

    bus.subscribe("created", handler)
    errors = await bus.publish(Event(name="created", payload={"value": "ok"}))

    assert errors == []
    assert seen == ["ok"]


@pytest.mark.asyncio
async def test_event_bus_offloads_sync_handlers() -> None:
    bus = InMemoryEventBus()
    event = Event(name="created", payload={})
    main_thread = threading.get_ident()
    handler_threads: list[int] = []

    def handler(value: Event) -> None:
        assert value is event
        handler_threads.append(threading.get_ident())

    bus.subscribe("created", handler)

    assert await bus.publish(event) == []
    assert len(handler_threads) == 1
    assert handler_threads[0] != main_thread


@pytest.mark.parametrize("backend", ["rabbitmq", "redis_streams"])
@pytest.mark.asyncio
async def test_broker_event_buses_offload_sync_handlers(
    backend: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    main_thread = threading.get_ident()
    handler_threads: list[int] = []

    def handler(_event: Event) -> None:
        handler_threads.append(threading.get_ident())

    if backend == "rabbitmq":
        monkeypatch.setattr("apyra.events.rabbitmq.aio_pika", object())
        bus = RabbitMQEventBus(connection=object())
    else:
        bus = RedisStreamEventBus(object())  # type: ignore[arg-type]

    await bus._dispatch([handler], Event(name="created", payload={}))

    assert len(handler_threads) == 1
    assert handler_threads[0] != main_thread


@pytest.mark.asyncio
async def test_cancelled_dispatch_waits_for_running_sync_handler(
    caplog: pytest.LogCaptureFixture,
) -> None:
    worker_started = threading.Event()
    release_worker = threading.Event()
    worker_finished = threading.Event()

    def blocking_handler(_event: Event) -> None:
        worker_started.set()
        try:
            release_worker.wait(timeout=2)
        finally:
            worker_finished.set()
        raise RuntimeError("worker failed after cancellation")

    task = asyncio.create_task(invoke_handler(blocking_handler, Event(name="created", payload={})))
    assert await asyncio.wait_for(asyncio.to_thread(worker_started.wait, 1), timeout=2)

    task.cancel()
    await asyncio.sleep(0)
    task.cancel()
    await asyncio.sleep(0)

    waited_for_worker = not task.done()
    release_worker.set()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task, timeout=2)
    assert waited_for_worker
    assert worker_finished.is_set()
    assert "worker failed after cancellation" in caplog.text


@pytest.mark.asyncio
async def test_sync_event_handler_can_return_an_awaitable() -> None:
    handled: list[str] = []

    def handler(_event: Event):
        async def finish() -> None:
            handled.append("done")

        return finish()

    await invoke_handler(handler, Event(name="created", payload={}))

    assert handled == ["done"]


class RedeliveredMessage:
    body = b'{"name":"created","payload":{"value":"ok"}}'

    def __init__(self) -> None:
        self.attempts = 0

    def process(self, *, requeue: bool) -> Self:
        assert requeue
        return self

    async def __aenter__(self) -> None:
        self.attempts += 1

    async def __aexit__(self, exc_type: object, exc: object, traceback: object) -> bool:
        return False


class RedeliveringQueue:
    def __init__(self, message: RedeliveredMessage) -> None:
        self.message = message

    def iterator(self) -> Self:
        return self

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, exc_type: object, exc: object, traceback: object) -> bool:
        return False

    def __aiter__(self) -> Self:
        self.attempts = 0
        return self

    async def __anext__(self) -> RedeliveredMessage:
        if self.attempts == 2:
            raise StopAsyncIteration
        self.attempts += 1
        return self.message


@pytest.mark.asyncio
async def test_rabbitmq_consumer_continues_after_requeued_handler_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bus = RabbitMQEventBus(connection=object())
    message = RedeliveredMessage()
    bus._queue = RedeliveringQueue(message)
    seen: list[str] = []
    calls = 0

    async def connect() -> None:
        return None

    async def no_delay(_seconds: float) -> None:
        return None

    async def handler(event: Event) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("temporary handler failure")
        seen.append(str(event.payload["value"]))
        bus._closed = True

    monkeypatch.setattr(bus, "_connect", connect)
    monkeypatch.setattr("apyra.events.rabbitmq.asyncio.sleep", no_delay)
    bus._handlers["created"].append(handler)

    await bus._consume()

    assert calls == 2
    assert seen == ["ok"]
    assert message.attempts == 2


@pytest.mark.asyncio
async def test_rabbitmq_consumer_skips_malformed_messages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bus = RabbitMQEventBus(connection=object())
    processed = 0
    handler_calls = 0

    class MalformedMessage:
        body = b"not json"

        class ProcessContext:
            async def __aenter__(self) -> None:
                nonlocal processed
                processed += 1

            async def __aexit__(self, *_args: object) -> bool:
                return False

        def process(self, *, requeue: bool) -> ProcessContext:
            assert requeue
            return self.ProcessContext()

    class OneMalformedMessageQueue:
        def iterator(self) -> Self:
            return self

        async def __aenter__(self) -> Self:
            return self

        async def __aexit__(self, *_args: object) -> bool:
            return False

        def __aiter__(self) -> Self:
            self.sent = False
            return self

        async def __anext__(self) -> MalformedMessage:
            if self.sent:
                bus._closed = True
                raise StopAsyncIteration
            self.sent = True
            return MalformedMessage()

    async def connect() -> None:
        return None

    async def handler(_event: Event) -> None:
        nonlocal handler_calls
        handler_calls += 1

    monkeypatch.setattr(bus, "_connect", connect)
    bus._queue = OneMalformedMessageQueue()
    bus._handlers["created"].append(handler)

    await bus._consume()

    assert processed == 1
    assert handler_calls == 0


@pytest.mark.asyncio
async def test_rabbitmq_waits_for_sibling_handlers_before_requeue() -> None:
    bus = RabbitMQEventBus(connection=object())
    sibling_started = asyncio.Event()
    release_sibling = asyncio.Event()
    attempts = 0
    active_siblings = 0
    sibling_cancellations = 0

    async def flaky_handler(_event: Event) -> None:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            await sibling_started.wait()
            raise RuntimeError("temporary handler failure")

    async def sibling_handler(_event: Event) -> None:
        nonlocal active_siblings, sibling_cancellations
        active_siblings += 1
        sibling_started.set()
        try:
            await release_sibling.wait()
        except asyncio.CancelledError:
            sibling_cancellations += 1
            raise
        finally:
            active_siblings -= 1

    with pytest.raises(ExceptionGroup):
        await bus._dispatch([flaky_handler, sibling_handler], Event(name="created", payload={}))

    if active_siblings:
        release_sibling.set()
        await asyncio.sleep(0)

    assert active_siblings == 0
    assert sibling_cancellations == 1


@pytest.mark.asyncio
async def test_rabbitmq_close_attempts_connection_after_channel_close_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("apyra.events.rabbitmq.aio_pika", object())
    bus = RabbitMQEventBus(connection=object())

    class FailingChannel:
        async def close(self) -> None:
            raise RuntimeError("channel close failed")

    class Connection:
        closed = False

        async def close(self) -> None:
            self.closed = True

    connection = Connection()
    bus._channel = FailingChannel()
    bus._connection = connection

    with pytest.raises(RuntimeError, match="channel close failed"):
        await bus.close()

    assert connection.closed
    assert bus._channel is None
    assert bus._connection is None


class EmptyQueue:
    def iterator(self) -> Self:
        return self

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, exc_type: object, exc: object, traceback: object) -> bool:
        return False

    def __aiter__(self) -> Self:
        return self

    async def __anext__(self) -> RedeliveredMessage:
        raise StopAsyncIteration


@pytest.mark.asyncio
async def test_rabbitmq_consumer_retries_setup_failure(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    bus = RabbitMQEventBus(connection=object())
    calls = 0

    async def connect() -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("temporary connection failure")
        bus._queue = EmptyQueue()
        bus._closed = True

    async def no_delay(_seconds: float) -> None:
        return None

    class FailingChannel:
        close_attempted = False

        async def close(self) -> None:
            self.close_attempted = True
            raise RuntimeError("temporary close failure")

    channel = FailingChannel()
    bus._channel = channel

    monkeypatch.setattr(bus, "_connect", connect)
    monkeypatch.setattr("apyra.events.rabbitmq.asyncio.sleep", no_delay)

    await bus._consume()

    assert calls == 2
    assert channel.close_attempted
    assert "RabbitMQ consumer failed; retrying in one second" in caplog.text


@pytest.mark.asyncio
async def test_rabbitmq_consumer_returns_when_message_processing_is_cancelled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bus = RabbitMQEventBus(connection=object())
    entered = False

    class CancelledMessage:
        body = b"{}"

        class ProcessContext:
            async def __aenter__(self) -> None:
                nonlocal entered
                entered = True
                raise asyncio.CancelledError

            async def __aexit__(self, *_args: object) -> bool:
                return False

        def process(self, *, requeue: bool) -> ProcessContext:
            assert requeue
            return self.ProcessContext()

    class OneCancelledMessageQueue:
        def iterator(self) -> Self:
            return self

        async def __aenter__(self) -> Self:
            return self

        async def __aexit__(self, *_args: object) -> bool:
            return False

        def __aiter__(self) -> Self:
            return self

        async def __anext__(self) -> CancelledMessage:
            return CancelledMessage()

    async def connect() -> None:
        return None

    monkeypatch.setattr(bus, "_connect", connect)
    bus._queue = OneCancelledMessageQueue()

    await bus._consume()

    assert entered


class FailingRedisClient:
    def __init__(self) -> None:
        self.read_count = 0
        self.read_ids: list[str] = []

    async def xadd(self, name: str, fields: dict[str, str], **kwargs: object) -> str:
        return "1-0"

    async def xrevrange(self, name: str, *, count: int) -> list[tuple[str, dict[str, str]]]:
        assert name == "apyra:events"
        assert count == 1
        return []

    async def xread(self, streams: dict[str, str], **kwargs: object) -> list[object]:
        self.read_count += 1
        self.read_ids.append(streams["apyra:events"])
        if self.read_count == 1:
            fields = {"name": "created", "payload": '{"value":"ok"}'}
            return [("apyra:events", [("1-0", fields)])]
        raise asyncio.CancelledError

    async def aclose(self) -> None:
        return None


class ReconnectingRedisClient:
    def __init__(self) -> None:
        self.read_count = 0
        self.event_available = asyncio.Event()
        self.read_ids: list[str] = []

    async def xadd(self, name: str, fields: dict[str, str], **kwargs: object) -> str:
        return "1-0"

    async def xrevrange(self, name: str, *, count: int) -> list[tuple[str, dict[str, str]]]:
        assert name == "apyra:events"
        assert count == 1
        return [("7-0", {})]

    async def xread(self, streams: dict[str, str], **kwargs: object) -> list[object]:
        self.read_count += 1
        self.read_ids.append(streams["apyra:events"])
        if self.read_count == 1:
            raise ConnectionError("temporary Redis outage")
        if self.read_count == 2:
            assert streams["apyra:events"] == "7-0"
            return []
        if self.read_count == 3:
            assert streams["apyra:events"] == "7-0"
            fields = {"name": "created", "payload": '{"value":"reconnected"}'}
            return [("apyra:events", [("8-0", fields)])]
        await self.event_available.wait()
        raise asyncio.CancelledError

    async def aclose(self) -> None:
        self.event_available.set()


@pytest.mark.asyncio
async def test_redis_stream_close_retries_until_closed_and_rejects_operations() -> None:
    class Client:
        close_calls = 0

        async def xadd(
            self,
            name: str,
            fields: dict[str, str],
            *,
            maxlen: int | None = None,
            approximate: bool = True,
        ) -> str:
            return "1-0"

        async def xrevrange(self, name: str, *, count: int) -> list[tuple[str, dict[str, str]]]:
            return []

        async def xread(
            self,
            streams: dict[str, str],
            *,
            count: int | None = None,
            block: int | None = None,
        ) -> list[object] | None:
            return []

        async def aclose(self) -> None:
            self.close_calls += 1
            if self.close_calls == 1:
                raise RuntimeError("temporary close failure")

    client = Client()
    bus = RedisStreamEventBus(client)
    with pytest.raises(RuntimeError, match="temporary close failure"):
        await bus.close()
    await bus.close()
    await bus.close()

    assert client.close_calls == 2
    with pytest.raises(RuntimeError, match="event bus is closed"):
        bus.subscribe("created", lambda _event: None)
    with pytest.raises(RuntimeError, match="event bus is closed"):
        await bus.publish(Event(name="created", payload={}))


@pytest.mark.asyncio
async def test_redis_stream_retries_failed_event_before_advancing_cursor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = FailingRedisClient()
    bus = RedisStreamEventBus(client)
    calls = 0
    seen: list[str] = []

    async def no_delay(_seconds: float) -> None:
        return None

    async def handler(event: Event) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("temporary handler failure")
        seen.append(str(event.payload["value"]))

    monkeypatch.setattr("apyra.events.redis_streams.asyncio.sleep", no_delay)
    bus._handlers["created"].append(handler)

    await bus._read_loop()

    assert calls == 2
    assert seen == ["ok"]
    assert client.read_count == 2
    assert client.read_ids == ["0-0", "1-0"]


@pytest.mark.asyncio
async def test_redis_stream_waits_for_sibling_handlers_before_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class SingleEventClient:
        reads = 0

        async def xrevrange(self, _name: str, *, count: int) -> list[tuple[str, dict[str, str]]]:
            return []

        async def xread(self, _streams: dict[str, str], **_kwargs: object) -> list[object] | None:
            self.reads += 1
            if self.reads > 2:
                raise asyncio.CancelledError
            fields = {"name": "created", "payload": "{}"}
            return [("events", [("1-0", fields)])]

        async def aclose(self) -> None:
            return None

    bus = RedisStreamEventBus(SingleEventClient())  # type: ignore[arg-type]
    sibling_started = asyncio.Event()
    release_sibling = asyncio.Event()
    delivered = asyncio.Event()
    attempts = 0
    active_siblings = 0
    max_active_siblings = 0
    sibling_cancellations = 0

    async def flaky_handler(_event: Event) -> None:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            await sibling_started.wait()
            raise RuntimeError("temporary handler failure")
        delivered.set()

    async def sibling_handler(_event: Event) -> None:
        nonlocal active_siblings, max_active_siblings, sibling_cancellations
        active_siblings += 1
        max_active_siblings = max(max_active_siblings, active_siblings)
        sibling_started.set()
        if attempts > 1:
            release_sibling.set()
        try:
            await release_sibling.wait()
        except asyncio.CancelledError:
            sibling_cancellations += 1
            raise
        finally:
            active_siblings -= 1

    bus.subscribe("created", flaky_handler)
    bus.subscribe("created", sibling_handler)

    async def no_delay(_seconds: float) -> None:
        return None

    monkeypatch.setattr("apyra.events.redis_streams.asyncio.sleep", no_delay)
    await asyncio.wait_for(delivered.wait(), timeout=1)
    await bus.close()

    assert attempts == 2
    assert max_active_siblings == 1
    assert sibling_cancellations == 1


@pytest.mark.asyncio
async def test_redis_stream_recovers_after_temporary_read_failure(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    client = ReconnectingRedisClient()
    bus = RedisStreamEventBus(client)
    delivered = asyncio.Event()
    seen: list[str] = []

    async def no_delay(_seconds: float) -> None:
        return None

    async def handler(event: Event) -> None:
        seen.append(str(event.payload["value"]))
        delivered.set()

    monkeypatch.setattr("apyra.events.redis_streams.asyncio.sleep", no_delay)
    bus.subscribe("created", handler)
    await asyncio.wait_for(delivered.wait(), timeout=1)
    await bus.close()

    assert seen == ["reconnected"]
    assert client.read_count == 3
    assert client.read_ids == ["7-0", "7-0", "7-0"]
    assert "Redis event reader failed; retrying in one second" in caplog.text


@pytest.mark.asyncio
async def test_redis_stream_skips_invalid_utf8_fields_and_continues() -> None:
    class MalformedThenValidRedisClient:
        reads = 0

        async def xrevrange(self, _name: str, *, count: int) -> list[tuple[str, dict[str, str]]]:
            return []

        async def xread(self, _streams: dict[str, str], **_kwargs: object) -> list[object]:
            self.reads += 1
            if self.reads == 1:
                return [("events", [("1-0", {b"name": b"created", b"payload": b"\xff"})])]
            if self.reads == 2:
                return [("events", [("2-0", {b"name": b"created", b"payload": b"{}"})])]
            raise AssertionError("reader should stop after dispatching the valid event")

        async def aclose(self) -> None:
            return None

    client = MalformedThenValidRedisClient()
    bus = RedisStreamEventBus(client)  # type: ignore[arg-type]
    seen: list[str] = []

    async def handler(event: Event) -> None:
        seen.append(event.name)
        bus._closed = True

    bus._handlers["created"].append(handler)

    await bus._read_loop()

    assert client.reads == 2
    assert seen == ["created"]
    assert bus._last_id == "2-0"


@pytest.mark.asyncio
async def test_redis_stream_defaults_deeply_nested_payload_and_continues() -> None:
    class DeepPayloadThenValidRedisClient:
        reads = 0

        async def xrevrange(self, _name: str, *, count: int) -> list[tuple[str, dict[str, str]]]:
            return []

        async def xread(self, _streams: dict[str, str], **_kwargs: object) -> list[object]:
            self.reads += 1
            if self.reads == 1:
                return [
                    (
                        "events",
                        [("1-0", {"name": "created", "payload": "[" * 10000 + "0" + "]" * 10000})],
                    )
                ]
            if self.reads == 2:
                return [("events", [("2-0", {"name": "created", "payload": '{"id":2}'})])]
            raise AssertionError("reader should stop after dispatching the valid event")

        async def aclose(self) -> None:
            return None

    client = DeepPayloadThenValidRedisClient()
    bus = RedisStreamEventBus(client)  # type: ignore[arg-type]
    payloads: list[dict[str, object]] = []

    async def handler(event: Event) -> None:
        payloads.append(event.payload)
        if event.payload.get("id") == 2:
            bus._closed = True

    bus._handlers["created"].append(handler)

    await bus._read_loop()

    assert client.reads == 2
    assert payloads == [{}, {"id": 2}]
    assert bus._last_id == "2-0"
