"""Memcached-backed JSON cache."""

from __future__ import annotations

import asyncio
import json
from typing import Any, Protocol

JSONValue = Any


class MemcachedClient(Protocol):
    def get(self, key: str) -> bytes | str | None: ...

    def set(self, key: str, value: bytes, expire: int = 0) -> object: ...

    def delete(self, key: str) -> object: ...

    def flush_all(self) -> object: ...

    def close(self) -> None: ...


class MemcachedCache:
    def __init__(
        self, client: MemcachedClient, *, key_prefix: str = "app", default_ttl_seconds: int = 300
    ) -> None:
        self._client = client
        self._prefix = key_prefix.strip(":")
        self._default_ttl = default_ttl_seconds

    def _key(self, key: str) -> str:
        return f"{self._prefix}:{key}" if self._prefix else key

    async def get(self, key: str) -> JSONValue | None:
        raw = await asyncio.to_thread(self._client.get, self._key(key))
        if raw is None:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        return json.loads(raw)

    async def set(self, key: str, value: JSONValue, *, ttl_seconds: int | None = None) -> None:
        ttl = self._default_ttl if ttl_seconds is None else ttl_seconds
        if ttl <= 0:
            await self.delete(key)
            return
        payload = json.dumps(value, separators=(",", ":")).encode("utf-8")
        await asyncio.to_thread(self._client.set, self._key(key), payload, ttl)

    async def delete(self, key: str) -> None:
        await asyncio.to_thread(self._client.delete, self._key(key))

    async def clear(self) -> None:
        await asyncio.to_thread(self._client.flush_all)

    async def close(self) -> None:
        await asyncio.to_thread(self._client.close)


__all__ = ["MemcachedCache", "MemcachedClient"]
