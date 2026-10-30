"""High-level cache manager."""

from __future__ import annotations

from .base import CacheClient
from .memory import InMemoryCache


class CacheManager:
    def __init__(self, client: CacheClient | None = None) -> None:
        self._client = client or InMemoryCache()

    @property
    def client(self) -> CacheClient:
        return self._client

    async def get(self, key: str) -> object | None:
        return await self._client.get(key)

    async def set(self, key: str, value: object, *, ttl_seconds: int | None = None) -> None:
        await self._client.set(key, value, ttl_seconds=ttl_seconds)

    async def delete(self, key: str) -> None:
        await self._client.delete(key)
