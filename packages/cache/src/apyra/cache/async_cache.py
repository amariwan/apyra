"""Async JSON cache contract and in-process implementation."""

from __future__ import annotations

from typing import Any, Protocol

from .memory_cache import MemoryTTLCache

JSONValue = Any


class AsyncCache(Protocol):
    async def get(self, key: str) -> JSONValue | None: ...

    async def set(self, key: str, value: JSONValue, *, ttl_seconds: int | None = None) -> None: ...

    async def delete(self, key: str) -> None: ...

    async def clear(self) -> None: ...

    async def close(self) -> None: ...


class MemoryAsyncCache:
    """Async facade over the process-local TTL cache."""

    def __init__(self, *, ttl_seconds: int = 300, max_entries: int = 1024) -> None:
        self._default_ttl = ttl_seconds
        self._default_cache = MemoryTTLCache[str, JSONValue](
            ttl_seconds=ttl_seconds, max_entries=max_entries
        )

    async def get(self, key: str) -> JSONValue | None:
        return self._default_cache.get(key)

    async def set(self, key: str, value: JSONValue, *, ttl_seconds: int | None = None) -> None:
        ttl = self._default_ttl if ttl_seconds is None else ttl_seconds
        self._default_cache.set(key, value, ttl_seconds=ttl)

    async def delete(self, key: str) -> None:
        self._default_cache.invalidate(key)

    async def clear(self) -> None:
        self._default_cache.clear()

    async def close(self) -> None:
        await self.clear()


__all__ = ["AsyncCache", "JSONValue", "MemoryAsyncCache"]
