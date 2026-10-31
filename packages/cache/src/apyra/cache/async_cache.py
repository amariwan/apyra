"""Async JSON cache contract and in-process implementation."""

from __future__ import annotations

from typing import Any, Protocol

from .memory_cache import MemoryTTLCache

JSONValue = Any


class AsyncCache(Protocol):
    """Async key-value cache contract with optional expiration."""

    async def get(self, key: str) -> JSONValue | None:
        """Return a cached value or ``None`` when the key is absent."""
        ...

    async def set(self, key: str, value: JSONValue, *, ttl_seconds: int | None = None) -> None:
        """Store a value, optionally overriding the backend's default TTL."""
        ...

    async def delete(self, key: str) -> None:
        """Remove one key if it exists."""
        ...

    async def clear(self) -> None:
        """Remove cached entries according to the backend's clear semantics."""
        ...

    async def close(self) -> None:
        """Release backend resources held by this cache."""
        ...


class MemoryAsyncCache:
    """Async facade over the process-local TTL cache."""

    def __init__(self, *, ttl_seconds: int = 300, max_entries: int = 1024) -> None:
        self._default_ttl = ttl_seconds
        self._default_cache = MemoryTTLCache[str, JSONValue](
            ttl_seconds=ttl_seconds, max_entries=max_entries
        )

    async def get(self, key: str) -> JSONValue | None:
        """Return a value from the process-local TTL cache."""
        return self._default_cache.get(key)

    async def set(self, key: str, value: JSONValue, *, ttl_seconds: int | None = None) -> None:
        """Store a value using the supplied TTL or configured default."""
        ttl = self._default_ttl if ttl_seconds is None else ttl_seconds
        self._default_cache.set(key, value, ttl_seconds=ttl)

    async def delete(self, key: str) -> None:
        """Remove one key from the process-local cache."""
        self._default_cache.invalidate(key)

    async def clear(self) -> None:
        """Remove every entry from the process-local cache."""
        self._default_cache.clear()

    async def close(self) -> None:
        """Clear entries; no external resource is held by this backend."""
        await self.clear()


__all__ = ["AsyncCache", "JSONValue", "MemoryAsyncCache"]
