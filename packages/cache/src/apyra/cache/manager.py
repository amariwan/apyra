"""High-level cache manager."""

from __future__ import annotations

from .base import CacheClient
from .memory import InMemoryCache


class CacheManager:
    """Delegate basic cache operations to an injected or default client."""

    def __init__(self, client: CacheClient | None = None) -> None:
        self._client = client if client is not None else InMemoryCache()

    @property
    def client(self) -> CacheClient:
        """Return the client used by this manager."""
        return self._client

    async def get(self, key: str) -> object | None:
        """Return a cached value or ``None`` when the key is absent."""
        return await self._client.get(key)

    async def set(self, key: str, value: object, *, ttl_seconds: int | None = None) -> None:
        """Store a value with an optional time-to-live override."""
        await self._client.set(key, value, ttl_seconds=ttl_seconds)

    async def delete(self, key: str) -> None:
        """Remove a key from the configured client."""
        await self._client.delete(key)
