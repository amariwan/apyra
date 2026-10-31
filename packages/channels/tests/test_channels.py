import asyncio
import json
import os
import subprocess
import sys
from collections.abc import Generator
from types import SimpleNamespace
from typing import Any, cast

import pytest
from fastapi import WebSocket as FastAPIWebSocket

from apyra.channels import MemoryChannelLayer
from apyra.channels import factory as channel_factory
from apyra.channels.factory import close_channel_layer, get_channel_layer
from apyra.channels.redis import RedisChannelSubscription
from apyra.channels.settings import ChannelBackend, ChannelSettings
from apyra.channels.websocket import WebSocketChannel


def test_channel_settings_repr_redacts_redis_credentials_without_changing_value() -> None:
    redis_url = "redis://user:channel-secret@cache.example/0"
    settings = ChannelSettings(CHANNELS_REDIS_URL=redis_url)

    assert "channel-secret" not in repr(settings)
    assert settings.CHANNELS_REDIS_URL == redis_url


def test_channels_import_does_not_hide_unrelated_import_error() -> None:
    script = """
import builtins
original_import = builtins.__import__
def failing_import(name, globals=None, locals=None, fromlist=(), level=0):
    if name == 'websocket' and level == 1 and globals and globals.get('__package__') == 'apyra.channels':
        raise ImportError('synthetic adapter import failure')
    return original_import(name, globals, locals, fromlist, level)
builtins.__import__ = failing_import
import apyra.channels
"""
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join(sys.path)
    result = subprocess.run(
        [sys.executable, "-c", script],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )

    assert result.returncode != 0
    assert "synthetic adapter import failure" in result.stderr


@pytest.fixture(autouse=True)
def clear_channel_layer_cache() -> Generator[None, None, None]:
    get_channel_layer.cache_clear()
    yield
    get_channel_layer.cache_clear()


@pytest.mark.asyncio
async def test_publish_subscribe() -> None:
    layer = MemoryChannelLayer()
    subscription = await layer.subscribe("events")
    task = asyncio.create_task(anext(subscription))
    await asyncio.sleep(0)
    await layer.publish("events", {"hello": "world"})
    result = await asyncio.wait_for(task, timeout=1)
    assert result == {"hello": "world"}
    await subscription.close()


@pytest.mark.asyncio
async def test_redis_subscription_close_finishes_after_draining_full_queue() -> None:
    message_ready = asyncio.Event()

    class FirstMessagePubSub:
        def __init__(self) -> None:
            self._sent = False

        async def get_message(self, **options: object) -> dict[str, object] | None:
            if not self._sent:
                self._sent = True
                message_ready.set()
                return {"data": json.dumps({"event": "ready"})}
            await asyncio.Event().wait()

        async def subscribe(self, *channels: str) -> None:
            pass

        async def unsubscribe(self, *channels: str) -> None:
            pass

        async def aclose(self) -> None:
            pass

    subscription = RedisChannelSubscription(FirstMessagePubSub(), "events", queue_size=1)
    await asyncio.wait_for(message_ready.wait(), timeout=1)
    await subscription.close()

    assert await asyncio.wait_for(anext(subscription), timeout=1) == {"event": "ready"}
    with pytest.raises(StopAsyncIteration):
        await asyncio.wait_for(anext(subscription), timeout=1)


@pytest.mark.asyncio
async def test_redis_layer_closes_pubsub_when_subscribe_fails(
    caplog: pytest.LogCaptureFixture,
) -> None:
    closed = False

    class FailingSubscribePubSub:
        async def get_message(self, **options: object) -> dict[str, object] | None:
            return None

        async def subscribe(self, *channels: str) -> None:
            raise ConnectionError("subscribe failed")

        async def unsubscribe(self, *channels: str) -> None:
            pass

        async def aclose(self) -> None:
            nonlocal closed
            closed = True
            raise OSError("close failed")

    class Client:
        def pubsub(self) -> FailingSubscribePubSub:
            return FailingSubscribePubSub()

        async def publish(self, channel: str, message: str) -> int:
            return 0

        async def aclose(self) -> None:
            pass

    with pytest.raises(ConnectionError, match="subscribe failed"):
        await channel_factory.RedisChannelLayer(Client()).subscribe("events")

    assert closed
    assert "close failed" in caplog.text


@pytest.mark.asyncio
async def test_redis_subscription_drops_oldest_message_and_passes_malformed_json() -> None:
    ready = asyncio.Event()

    class QueuedPubSub:
        def __init__(self) -> None:
            self._messages: list[dict[str, object] | None] = [
                None,
                {"data": b'{"sequence": 1}'},
                {"data": '{"sequence": 2}'},
                {"data": "not-json"},
            ]

        async def get_message(self, **options: object) -> dict[str, object] | None:
            if self._messages:
                message = self._messages.pop(0)
                if not self._messages:
                    ready.set()
                return message
            await asyncio.Event().wait()

        async def subscribe(self, *channels: str) -> None:
            pass

        async def unsubscribe(self, *channels: str) -> None:
            pass

        async def aclose(self) -> None:
            pass

    subscription = RedisChannelSubscription(QueuedPubSub(), "events", queue_size=2)
    await asyncio.wait_for(ready.wait(), timeout=1)
    await subscription.close()

    assert await asyncio.wait_for(anext(subscription), timeout=1) == {"sequence": 2}
    assert await asyncio.wait_for(anext(subscription), timeout=1) == "not-json"
    with pytest.raises(StopAsyncIteration):
        await asyncio.wait_for(anext(subscription), timeout=1)


@pytest.mark.asyncio
async def test_redis_layer_manages_subscription_and_client_lifecycles() -> None:
    subscribed: list[str] = []
    unsubscribed: list[str] = []
    client_closed = False

    class IdlePubSub:
        async def get_message(self, **options: object) -> dict[str, object] | None:
            await asyncio.Event().wait()

        async def subscribe(self, *channels: str) -> None:
            subscribed.extend(channels)

        async def unsubscribe(self, *channels: str) -> None:
            unsubscribed.extend(channels)

        async def aclose(self) -> None:
            pass

    class Client:
        def pubsub(self) -> IdlePubSub:
            return IdlePubSub()

        async def publish(self, channel: str, message: str) -> int:
            return 0

        async def aclose(self) -> None:
            nonlocal client_closed
            client_closed = True

    layer = channel_factory.RedisChannelLayer(Client(), prefix="tenant:events:")
    subscription = await layer.subscribe("orders")

    assert subscribed == ["tenant:events:orders"]
    assert subscription.__aiter__() is subscription
    await subscription.close()
    await subscription.close()
    await layer.close()

    assert unsubscribed == ["tenant:events:orders"]
    assert client_closed


@pytest.mark.asyncio
async def test_redis_subscription_closes_pubsub_when_unsubscribe_fails() -> None:
    closed = False

    class FailingUnsubscribePubSub:
        async def get_message(self, **options: object) -> dict[str, object] | None:
            await asyncio.Event().wait()

        async def subscribe(self, *channels: str) -> None:
            pass

        async def unsubscribe(self, *channels: str) -> None:
            raise ConnectionError("redis disconnected")

        async def aclose(self) -> None:
            nonlocal closed
            closed = True

    subscription = RedisChannelSubscription(FailingUnsubscribePubSub(), "events")

    with pytest.raises(ConnectionError, match="redis disconnected"):
        await subscription.close()

    assert closed


@pytest.mark.asyncio
async def test_redis_subscription_stops_cleanly_when_reader_fails(
    caplog: pytest.LogCaptureFixture,
) -> None:
    class RedisFailure(Exception):
        pass

    class FailingPubSub:
        async def get_message(self, **options: object) -> dict[str, object] | None:
            raise RedisFailure("connection lost")

        async def subscribe(self, *channels: str) -> None:
            pass

        async def unsubscribe(self, *channels: str) -> None:
            pass

        async def aclose(self) -> None:
            pass

    subscription = RedisChannelSubscription(FailingPubSub(), "events")

    with pytest.raises(StopAsyncIteration):
        await asyncio.wait_for(anext(subscription), timeout=1)
    assert subscription._reader.exception() is None
    assert "connection lost" in caplog.text
    await subscription.close()


def test_channel_factory_returns_none_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        channel_factory, "get_channel_settings", lambda: ChannelSettings(CHANNELS_ENABLED=False)
    )

    assert get_channel_layer() is None


@pytest.mark.asyncio
async def test_channel_factory_close_is_safe_before_initialization() -> None:
    await close_channel_layer()


@pytest.mark.asyncio
async def test_channel_factory_closes_cached_memory_layer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        channel_factory,
        "get_channel_settings",
        lambda: ChannelSettings(CHANNELS_ENABLED=True, CHANNELS_BACKEND=ChannelBackend.MEMORY),
    )
    layer = get_channel_layer()
    assert isinstance(layer, MemoryChannelLayer)
    subscription = await layer.subscribe("events")
    waiting = asyncio.create_task(anext(subscription))

    await close_channel_layer()

    with pytest.raises(StopAsyncIteration):
        await asyncio.wait_for(waiting, timeout=1)
    assert get_channel_layer.cache_info().currsize == 0


def test_channel_factory_reports_missing_redis_extra(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        channel_factory,
        "get_channel_settings",
        lambda: ChannelSettings(
            CHANNELS_ENABLED=True,
            CHANNELS_BACKEND=ChannelBackend.REDIS,
            CHANNELS_REDIS_URL="redis://localhost",
        ),
    )

    def missing_redis(name: str) -> Any:
        raise ModuleNotFoundError("No module named 'redis'", name="redis")

    monkeypatch.setattr(channel_factory, "import_module", missing_redis)

    with pytest.raises(RuntimeError, match="Redis channels require the 'redis' project extra"):
        get_channel_layer()


@pytest.mark.asyncio
async def test_channel_factory_builds_redis_layer(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str | None, bool]] = []
    published: list[str] = []

    class RedisClient:
        async def publish(self, channel: str, message: str) -> int:
            published.append(channel)
            return 1

        def pubsub(self) -> Any:
            raise NotImplementedError

        async def aclose(self) -> None:
            pass

    class RedisFactory:
        @staticmethod
        def from_url(url: str | None, *, decode_responses: bool) -> object:
            calls.append((url, decode_responses))
            return RedisClient()

    monkeypatch.setattr(
        channel_factory,
        "get_channel_settings",
        lambda: ChannelSettings(
            CHANNELS_ENABLED=True,
            CHANNELS_BACKEND=ChannelBackend.REDIS,
            CHANNELS_REDIS_URL="redis://localhost",
            CHANNELS_PREFIX="tenant:events:",
        ),
    )

    def fake_import_module(_name: str) -> Any:
        return SimpleNamespace(Redis=RedisFactory)

    monkeypatch.setattr(channel_factory, "import_module", fake_import_module)

    layer = get_channel_layer()

    assert layer is not None
    assert calls == [("redis://localhost", False)]
    assert await layer.publish("orders", {"id": 1}) == 1
    assert published == ["tenant:events:orders"]


@pytest.mark.asyncio
async def test_websocket_disconnect_closes_subscription() -> None:
    class BlockingSubscription:
        closed = False

        def __aiter__(self) -> Any:
            return self

        async def __anext__(self) -> Any:
            await asyncio.Event().wait()

        async def close(self) -> None:
            self.closed = True

    class Layer:
        def __init__(self) -> None:
            self.subscription = BlockingSubscription()

        async def subscribe(self, channel: str) -> Any:
            return self.subscription

        async def publish(self, channel: str, message: Any) -> int:
            return 0

        async def close(self) -> None:
            pass

    class DisconnectedWebSocket:
        accepted = False
        receive_called = False

        async def accept(self) -> None:
            self.accepted = True

        async def receive(self) -> dict[str, str]:
            assert self.accepted
            self.receive_called = True
            return {"type": "websocket.disconnect"}

        async def send_json(self, message: Any) -> None:
            raise AssertionError("no messages should be sent")

    layer = Layer()
    websocket = DisconnectedWebSocket()

    await asyncio.wait_for(
        WebSocketChannel(layer).stream(cast(FastAPIWebSocket, websocket), "events"), 1
    )

    assert websocket.accepted
    assert websocket.receive_called
    assert layer.subscription.closed


@pytest.mark.asyncio
async def test_websocket_channel_forwards_messages() -> None:
    class OneMessageSubscription:
        def __init__(self) -> None:
            self.sent = False
            self.closed = False

        def __aiter__(self) -> Any:
            return self

        async def __anext__(self) -> Any:
            if self.sent:
                raise StopAsyncIteration
            self.sent = True
            return {"event": "ready"}

        async def close(self) -> None:
            self.closed = True

    class Layer:
        def __init__(self) -> None:
            self.subscription = OneMessageSubscription()

        async def subscribe(self, channel: str) -> Any:
            return self.subscription

        async def publish(self, channel: str, message: Any) -> int:
            return 0

        async def close(self) -> None:
            pass

    class WebSocket:
        def __init__(self) -> None:
            self.sent = asyncio.Event()
            self.messages: list[Any] = []
            self.receive_count = 0

        async def accept(self) -> None:
            pass

        async def receive(self) -> dict[str, str]:
            self.receive_count += 1
            if self.receive_count == 1:
                return {"type": "websocket.receive", "text": "ignored"}
            await self.sent.wait()
            return {"type": "websocket.disconnect"}

        async def send_json(self, message: Any) -> None:
            self.messages.append(message)
            self.sent.set()

    layer = Layer()
    websocket = WebSocket()

    await asyncio.wait_for(
        WebSocketChannel(layer).stream(cast(FastAPIWebSocket, websocket), "events"), 1
    )

    assert websocket.messages == [{"event": "ready"}]
    assert websocket.receive_count == 2
    assert layer.subscription.closed
