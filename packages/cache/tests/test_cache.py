import pytest

from apyra.cache import MemoryAsyncCache


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
