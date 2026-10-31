import builtins
import sys
from collections.abc import AsyncIterator
from types import ModuleType, SimpleNamespace

import pytest

from apyra.cache import MemoryAsyncCache
from apyra.cache import factory as cache_factory
from apyra.cache.base import CacheClient
from apyra.cache.manager import CacheManager
from apyra.cache.memory_cache import MemoryTTLCache
from apyra.cache.redis_cache import RedisCache
from apyra.cache.settings import CacheBackend, CacheSettings


def test_cache_settings_repr_redacts_redis_credentials_without_changing_value() -> None:
    redis_url = "redis://user:redis-secret@cache.example/0"
    settings = CacheSettings(cache_redis_url=redis_url)

    assert "redis-secret" not in repr(settings)
    assert settings.cache_redis_url == redis_url


@pytest.mark.asyncio
async def test_cache_ttl_expires() -> None:
    cache = MemoryAsyncCache(ttl_seconds=0)
    await cache.set("key", "value")
    assert await cache.get("key") is None


@pytest.mark.asyncio
async def test_cache_round_trip() -> None:
    cache = MemoryAsyncCache()
    await cache.set("key", {"a": 1})
    assert await cache.get("key") == {"a": 1}
    await cache.delete("key")
    assert await cache.get("key") is None


def test_memory_cache_get_or_set_caches_none() -> None:
    cache = MemoryTTLCache[str, str | None](ttl_seconds=30)
    calls = 0

    def factory() -> None:
        nonlocal calls
        calls += 1

    assert cache.get_or_set("key", factory) is None
    assert cache.get_or_set("key", factory) is None
    assert calls == 1


@pytest.mark.asyncio
async def test_cache_manager_delegates_operations_and_ttl() -> None:
    class RecordingClient:
        get_key: str | None = None
        set_call: tuple[str, object, int | None] | None = None
        deleted_key: str | None = None

        async def get(self, key: str) -> object | None:
            self.get_key = key
            return "cached"

        async def set(self, key: str, value: object, *, ttl_seconds: int | None = None) -> None:
            self.set_call = (key, value, ttl_seconds)

        async def delete(self, key: str) -> None:
            self.deleted_key = key

    client = RecordingClient()
    manager = CacheManager(client)

    assert await manager.get("read-key") == "cached"
    await manager.set("write-key", "value", ttl_seconds=30)
    await manager.delete("delete-key")

    assert client.get_key == "read-key"
    assert client.set_call == ("write-key", "value", 30)
    assert client.deleted_key == "delete-key"


def test_cache_manager_keeps_a_falsey_custom_client() -> None:
    class FalseyClient:
        def __bool__(self) -> bool:
            return False

        async def get(self, key: str) -> object | None:
            return None

        async def set(self, key: str, value: object, *, ttl_seconds: int | None = None) -> None:
            return None

        async def delete(self, key: str) -> None:
            return None

    client: CacheClient = FalseyClient()

    assert CacheManager(client).client is client


@pytest.mark.parametrize(
    ("servers", "expected_address"),
    [
        ("localhost:11211", ("localhost", 11211)),
        ("cache.example", ("cache.example", 11211)),
        ("cache.example:22122", ("cache.example", 22122)),
    ],
)
def test_memcached_backend_does_not_require_redis(
    monkeypatch: pytest.MonkeyPatch,
    servers: str,
    expected_address: tuple[str, int],
) -> None:
    from apyra.cache import factory

    client = object()
    addresses: list[tuple[str, int]] = []
    base_module = ModuleType("pymemcache.client.base")

    def create_client(address: tuple[str, int]) -> object:
        addresses.append(address)
        return client

    base_module.Client = create_client  # type: ignore[attr-defined]
    client_module = ModuleType("pymemcache.client")
    package_module = ModuleType("pymemcache")
    monkeypatch.setitem(sys.modules, "pymemcache", package_module)
    monkeypatch.setitem(sys.modules, "pymemcache.client", client_module)
    monkeypatch.setitem(sys.modules, "pymemcache.client.base", base_module)
    monkeypatch.setattr(
        factory,
        "get_cache_settings",
        lambda: SimpleNamespace(
            cache_enabled=True,
            cache_backend=CacheBackend.MEMCACHED,
            cache_memcached_servers=servers,
            cache_memcached_allow_server_flush=True,
            cache_max_entries=1024,
            cache_key_prefix="app",
            cache_default_ttl_seconds=300,
        ),
    )

    def reject_redis_import(name: str) -> ModuleType:
        if name == "redis.asyncio":
            raise AssertionError("Memcached must not import Redis")
        raise ImportError(name)

    monkeypatch.setattr(factory, "import_module", reject_redis_import)
    factory.get_cache.cache_clear()
    try:
        cache = factory.get_cache()
        assert cache._client is client  # type: ignore[attr-defined]
        assert cache._allow_server_flush is True  # type: ignore[attr-defined]
        assert addresses == [expected_address]
    finally:
        factory.get_cache.cache_clear()


def test_cache_factory_returns_configured_memory_backend(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = CacheSettings(
        cache_backend=CacheBackend.MEMORY,
        cache_default_ttl_seconds=47,
        cache_max_entries=13,
    )
    monkeypatch.setattr(cache_factory, "get_cache_settings", lambda: settings)
    cache_factory.get_cache.cache_clear()
    try:
        cache = cache_factory.get_cache()
        assert isinstance(cache, MemoryAsyncCache)
        assert cache._default_ttl == 47  # type: ignore[attr-defined]
    finally:
        cache_factory.get_cache.cache_clear()


@pytest.mark.asyncio
async def test_close_cache_is_safe_before_and_after_initialization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = CacheSettings(cache_backend=CacheBackend.MEMORY)
    monkeypatch.setattr(cache_factory, "get_cache_settings", lambda: settings)
    cache_factory.get_cache.cache_clear()

    try:
        await cache_factory.close_cache()
        cache = cache_factory.get_cache()
        await cache.set("key", "value")
        await cache_factory.close_cache()

        assert cache_factory.get_cache.cache_info().currsize == 0
        assert await cache.get("key") is None
    finally:
        cache_factory.get_cache.cache_clear()


@pytest.mark.asyncio
async def test_close_cache_retains_backend_when_close_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = CacheSettings(cache_backend=CacheBackend.MEMORY)
    monkeypatch.setattr(cache_factory, "get_cache_settings", lambda: settings)
    cache_factory.get_cache.cache_clear()
    cache = cache_factory.get_cache()
    attempts = 0

    async def fail_once() -> None:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("close failed")

    monkeypatch.setattr(cache, "close", fail_once)
    try:
        with pytest.raises(RuntimeError, match="close failed"):
            await cache_factory.close_cache()

        assert cache_factory.get_cache.cache_info().currsize == 1
        assert cache_factory.get_cache() is cache

        await cache_factory.close_cache()
        assert attempts == 2
        assert cache_factory.get_cache.cache_info().currsize == 0
    finally:
        cache_factory.get_cache.cache_clear()


def test_redis_backend_uses_configured_url_and_options(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = CacheSettings(
        cache_backend=CacheBackend.REDIS,
        cache_redis_url="redis://localhost:6379/4",
        cache_key_prefix="service",
        cache_default_ttl_seconds=81,
    )
    client = object()
    calls: list[tuple[str | None, bool]] = []

    class RedisFactory:
        @staticmethod
        def from_url(url: str | None, *, decode_responses: bool) -> object:
            calls.append((url, decode_responses))
            return client

    redis_module = ModuleType("redis.asyncio")
    redis_module.Redis = RedisFactory  # type: ignore[attr-defined]
    monkeypatch.setattr(cache_factory, "get_cache_settings", lambda: settings)

    def import_redis(_name: str) -> ModuleType:
        return redis_module

    monkeypatch.setattr(cache_factory, "import_module", import_redis)
    cache_factory.get_cache.cache_clear()
    try:
        cache = cache_factory.get_cache()
        assert isinstance(cache, RedisCache)
        assert cache._client is client  # type: ignore[attr-defined]
        assert cache._prefix == "service"  # type: ignore[attr-defined]
        assert cache._default_ttl == 81  # type: ignore[attr-defined]
        assert calls == [("redis://localhost:6379/4", False)]
    finally:
        cache_factory.get_cache.cache_clear()


def test_redis_backend_reports_missing_optional_dependency(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = CacheSettings(
        cache_backend=CacheBackend.REDIS,
        cache_redis_url="redis://localhost:6379/0",
    )

    def missing_redis(_name: str) -> ModuleType:
        raise ModuleNotFoundError("redis is unavailable", name="redis")

    monkeypatch.setattr(cache_factory, "get_cache_settings", lambda: settings)
    monkeypatch.setattr(cache_factory, "import_module", missing_redis)
    cache_factory.get_cache.cache_clear()
    try:
        with pytest.raises(RuntimeError, match="requires the 'redis' project extra"):
            cache_factory.get_cache()
    finally:
        cache_factory.get_cache.cache_clear()


def test_memcached_backend_reports_missing_optional_dependency(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = SimpleNamespace(
        cache_enabled=True,
        cache_backend=CacheBackend.MEMCACHED,
        cache_memcached_servers="localhost:11211",
        cache_max_entries=1024,
        cache_key_prefix="app",
        cache_default_ttl_seconds=300,
    )
    real_import = builtins.__import__

    def missing_memcached(
        name: str,
        globals: dict[str, object] | None = None,
        locals: dict[str, object] | None = None,
        fromlist: tuple[str, ...] | None = None,
        level: int = 0,
    ) -> object:
        if name == "pymemcache.client.base":
            raise ModuleNotFoundError("pymemcache is unavailable", name="pymemcache")
        return real_import(name, globals, locals, fromlist or (), level)

    monkeypatch.setattr(cache_factory, "get_cache_settings", lambda: settings)
    monkeypatch.setattr(builtins, "__import__", missing_memcached)
    cache_factory.get_cache.cache_clear()
    try:
        with pytest.raises(RuntimeError, match="requires the 'pymemcache' project extra"):
            cache_factory.get_cache()
    finally:
        cache_factory.get_cache.cache_clear()


@pytest.mark.asyncio
@pytest.mark.parametrize("backend", [CacheBackend.REDIS, CacheBackend.MEMCACHED])
async def test_disabled_cache_skips_backend_initialization(
    monkeypatch: pytest.MonkeyPatch, backend: CacheBackend
) -> None:
    settings = CacheSettings(
        cache_enabled=False,
        cache_backend=backend,
    )
    monkeypatch.setattr(cache_factory, "get_cache_settings", lambda: settings)

    def reject_backend_import(name: str) -> ModuleType:
        raise AssertionError(f"disabled cache must not import backend module: {name}")

    monkeypatch.setattr(cache_factory, "import_module", reject_backend_import)
    cache_factory.get_cache.cache_clear()
    try:
        cache = cache_factory.get_cache()
        assert isinstance(cache, MemoryAsyncCache)
        await cache.set("key", "value")
        assert await cache.get("key") is None
    finally:
        cache_factory.get_cache.cache_clear()


class FakeRedisClient:
    def __init__(self) -> None:
        self.values: dict[str, str | bytes] = {}
        self.expirations: dict[str, int | None] = {}
        self.delete_batches: list[int] = []
        self.closed = False
        self.expected_match: str | None = None
        self.scan_prefix: str | None = None

    async def get(self, key: str) -> str | bytes | None:
        return self.values.get(key)

    async def set(self, key: str, value: str, *, ex: int | None = None) -> object:
        self.values[key] = value
        self.expirations[key] = ex
        return True

    async def delete(self, *keys: str) -> object:
        self.delete_batches.append(len(keys))
        for key in keys:
            self.values.pop(key, None)
        return len(keys)

    async def scan_iter(self, *, match: str) -> AsyncIterator[str | bytes]:
        if self.expected_match is not None:
            assert match == self.expected_match
        prefix = self.scan_prefix if self.scan_prefix is not None else match[:-1]
        for index, key in enumerate(tuple(self.values)):
            if key.startswith(prefix):
                yield key.encode() if index % 2 else key

    async def aclose(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_redis_cache_round_trip_ttl_delete_and_close() -> None:
    client = FakeRedisClient()
    cache = RedisCache(client, key_prefix="app", default_ttl_seconds=60)

    await cache.set("object", {"value": 1})
    assert client.values["app:object"] == '{"value":1}'
    assert client.expirations["app:object"] == 60
    assert await cache.get("object") == {"value": 1}

    client.values["app:bytes"] = b'["decoded"]'
    assert await cache.get("bytes") == ["decoded"]

    await cache.set("object", "expired", ttl_seconds=0)
    assert await cache.get("object") is None
    await cache.set("to-delete", True, ttl_seconds=15)
    await cache.delete("to-delete")
    assert await cache.get("to-delete") is None

    await cache.close()
    assert client.closed


@pytest.mark.asyncio
async def test_redis_cache_clear_is_prefix_scoped_and_batched() -> None:
    client = FakeRedisClient()
    client.values.update({f"app:{index}": "value" for index in range(501)})
    client.values["application:keep"] = "other namespace"
    cache = RedisCache(client, key_prefix="app")

    await cache.clear()

    assert client.delete_batches == [500, 1]
    assert client.values == {"application:keep": "other namespace"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("key_prefix", "expected_match"),
    [
        ("tenant*", r"tenant\*:*"),
        ("tenant?", r"tenant\?:*"),
        ("tenant[1]", r"tenant\[1\]:*"),
        (r"tenant\one", r"tenant\\one:*"),
    ],
)
async def test_redis_cache_clear_escapes_glob_characters_in_prefix(
    key_prefix: str, expected_match: str
) -> None:
    client = FakeRedisClient()
    client.values.update({f"{key_prefix}:owned": "value", "tenant-other:keep": "other"})
    client.expected_match = expected_match
    client.scan_prefix = f"{key_prefix}:"
    cache = RedisCache(client, key_prefix=key_prefix)

    await cache.clear()

    assert client.values == {"tenant-other:keep": "other"}


@pytest.mark.asyncio
async def test_redis_cache_clear_with_empty_prefix_scans_all_keys() -> None:
    client = FakeRedisClient()
    client.values.update({"first": "one", "second": "two"})
    client.expected_match = "*"
    client.scan_prefix = ""
    cache = RedisCache(client, key_prefix="")

    await cache.clear()

    assert client.values == {}
