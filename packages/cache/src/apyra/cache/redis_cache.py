"""Redis-backed JSON cache."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any, Protocol

JSONValue = Any


class RedisClient(Protocol):
    """Subset of the async Redis client API required by ``RedisCache``."""

    async def get(self, key: str) -> bytes | str | None:
        """Return a stored value as bytes or text, or ``None`` on a miss."""
        ...

    async def set(self, key: str, value: str, *, ex: int | None = None) -> object:
        """Store text and optionally set its expiration in seconds."""
        ...

    async def delete(self, *keys: str) -> object:
        """Delete one or more keys."""
        ...

    def scan_iter(self, *, match: str) -> AsyncIterator[bytes | str]:
        """Iterate through keys matching a Redis glob pattern."""
        ...

    async def aclose(self) -> None:
        """Close the Redis connection pool owned by this client."""
        ...


class RedisCache:
    """JSON cache adapter that namespaces keys and supports expiration."""

    def __init__(
        self, client: RedisClient, *, key_prefix: str = "app", default_ttl_seconds: int = 300
    ) -> None:
        self._client = client
        self._prefix = key_prefix.strip(":")
        self._default_ttl = default_ttl_seconds

    def _key(self, key: str) -> str:
        return f"{self._prefix}:{key}" if self._prefix else key

    def _clear_pattern(self) -> str:
        if not self._prefix:
            return "*"
        escaped_prefix = self._prefix.replace("\\", "\\\\")
        for character in "*?[]":
            escaped_prefix = escaped_prefix.replace(character, f"\\{character}")
        return f"{escaped_prefix}:*"

    async def get(self, key: str) -> JSONValue | None:
        """Load and decode a cached JSON value, returning ``None`` on a miss."""
        raw = await self._client.get(self._key(key))
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
        await self._client.set(self._key(key), json.dumps(value, separators=(",", ":")), ex=ttl)

    async def delete(self, key: str) -> None:
        """Delete the namespaced key."""
        await self._client.delete(self._key(key))

    async def clear(self) -> None:
        """Delete keys in this cache namespace in bounded batches."""
        keys: list[str] = []
        async for raw_key in self._client.scan_iter(match=self._clear_pattern()):
            keys.append(raw_key.decode("utf-8") if isinstance(raw_key, bytes) else raw_key)
            if len(keys) == 500:
                await self._client.delete(*keys)
                keys.clear()
        if keys:
            await self._client.delete(*keys)

    async def close(self) -> None:
        """Close the underlying Redis client."""
        await self._client.aclose()


__all__ = ["RedisCache", "RedisClient"]
