import pytest

from apyra.cache import MemcachedCache


class FakeMemcachedClient:
    def __init__(self) -> None:
        self.data: dict[str, bytes] = {}
        self.flushed = False
        self.closed = False

    def get(self, key: str):
        return self.data.get(key)

    def set(self, key: str, value: bytes, expire: int = 0) -> object:
        self.data[key] = value
        return True

    def delete(self, key: str) -> object:
        self.data.pop(key, None)
        return True

    def flush_all(self) -> object:
        self.flushed = True
        self.data.clear()
        return True

    def close(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_memcached_cache_round_trip() -> None:
    client = FakeMemcachedClient()
    cache = MemcachedCache(client, key_prefix="app", default_ttl_seconds=300)

    await cache.set("key", {"value": 1})
    assert await cache.get("key") == {"value": 1}
    await cache.delete("key")
    assert await cache.get("key") is None

    await cache.set("key", "value")
    with pytest.raises(RuntimeError, match="server-wide Memcached flush is disabled"):
        await cache.clear()
    assert not client.flushed

    cache = MemcachedCache(client, key_prefix="app", allow_server_flush=True)
    await cache.clear()
    assert client.flushed
    assert await cache.get("key") is None

    await cache.close()
    assert client.closed


@pytest.mark.asyncio
async def test_memcached_server_flush_is_disabled_by_default() -> None:
    client = FakeMemcachedClient()
    cache = MemcachedCache(client)

    with pytest.raises(RuntimeError, match="server-wide Memcached flush is disabled"):
        await cache.clear()

    assert not client.flushed
