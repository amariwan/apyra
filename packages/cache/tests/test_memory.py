from __future__ import annotations

import pytest

from apyra.cache.memory import InMemoryCache


@pytest.mark.asyncio
async def test_in_memory_cache_returns_missing_and_non_expiring_values() -> None:
    cache = InMemoryCache()

    assert await cache.get("missing") is None
    await cache.set("key", {"ready": True})
    assert await cache.get("key") == {"ready": True}


@pytest.mark.asyncio
async def test_in_memory_cache_expires_values_at_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = [100.0]
    monkeypatch.setattr("apyra.cache.memory.time.monotonic", lambda: now[0])
    cache = InMemoryCache()
    await cache.set("key", "value", ttl_seconds=5)

    now[0] = 104.99
    assert await cache.get("key") == "value"

    now[0] = 105.0
    assert await cache.get("key") is None


@pytest.mark.asyncio
async def test_in_memory_cache_delete_is_idempotent() -> None:
    cache = InMemoryCache()
    await cache.set("key", "value")

    await cache.delete("key")
    await cache.delete("missing")

    assert await cache.get("key") is None
