"""Memcached-backed JSON cache."""

from __future__ import annotations

import asyncio
import json
from typing import Any, Protocol

JSONValue = Any


class MemcachedClient(Protocol):
    """Subset of the synchronous Memcached client API required by the adapter."""

    def get(self, key: str) -> bytes | str | None:
        """Return the stored value or ``None`` when the key is absent."""
        ...

    def set(self, key: str, value: bytes, expire: int = 0) -> object:
        """Store bytes with an optional expiration duration."""
        ...

    def delete(self, key: str) -> object:
        """Delete one key."""
        ...

    def flush_all(self) -> object:
        """Remove all values from the connected Memcached server."""
        ...

    def close(self) -> None:
        """Close the underlying synchronous client."""
        ...


class MemcachedCache:
    """JSON cache adapter that offloads blocking client calls to threads."""

    def __init__(
        self,
        client: MemcachedClient,
        *,
        key_prefix: str = "app",
        default_ttl_seconds: int = 300,
        allow_server_flush: bool = False,
    ) -> None:
        self._client = client
        self._prefix = key_prefix.strip(":")
        self._default_ttl = default_ttl_seconds
        self._allow_server_flush = allow_server_flush

    def _key(self, key: str) -> str:
        return f"{self._prefix}:{key}" if self._prefix else key

    async def get(self, key: str) -> JSONValue | None:
        """Load and decode a JSON value, returning ``None`` on a cache miss."""
        raw = await asyncio.to_thread(self._client.get, self._key(key))
        if raw is None:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        return json.loads(raw)

    async def set(self, key: str, value: JSONValue, *, ttl_seconds: int | None = None) -> None:
        """Encode and store a JSON value; nonpositive TTL deletes the key."""
        ttl = self._default_ttl if ttl_seconds is None else ttl_seconds
        if ttl <= 0:
            await self.delete(key)
            return
        payload = json.dumps(value, separators=(",", ":")).encode("utf-8")
        await asyncio.to_thread(self._client.set, self._key(key), payload, ttl)

    async def delete(self, key: str) -> None:
        """Delete the namespaced key."""
        await asyncio.to_thread(self._client.delete, self._key(key))

    async def clear(self) -> None:
        """Flush the connected Memcached server."""
        if not self._allow_server_flush:
            raise RuntimeError(
                "server-wide Memcached flush is disabled; configure "
                "CACHE_MEMCACHED_ALLOW_SERVER_FLUSH=true to enable it"
            )
        await asyncio.to_thread(self._client.flush_all)

    async def close(self) -> None:
        """Close the underlying Memcached client in a worker thread."""
        await asyncio.to_thread(self._client.close)


__all__ = ["MemcachedCache", "MemcachedClient"]
