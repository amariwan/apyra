"""Redis-backed JSON cache."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any, Protocol, cast

JSONValue = Any


class RedisClient(Protocol):
    async def get(self, key: str) -> bytes | str | None: ...

    async def set(self, key: str, value: str, *, ex: int | None = None) -> object: ...

    async def delete(self, *keys: str) -> object: ...

    def scan_iter(self, *, match: str) -> AsyncIterator[bytes | str]: ...

    async def aclose(self) -> None: ...


class RedisCache:
    def __init__(
        self, client: RedisClient, *, key_prefix: str = "app", default_ttl_seconds: int = 300
    ) -> None:
        self._client = client
        self._prefix = key_prefix.strip(":")
        self._default_ttl = default_ttl_seconds

    def _key(self, key: str) -> str:
        return f"{self._prefix}:{key}" if self._prefix else key

    async def get(self, key: str) -> JSONValue | None:
        raw = await self._client.get(self._key(key))
        if raw is None:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        return cast(JSONValue, json.loads(raw))

    async def set(self, key: str, value: JSONValue, *, ttl_seconds: int | None = None) -> None:
        ttl = self._default_ttl if ttl_seconds is None else ttl_seconds
        if ttl <= 0:
            await self.delete(key)
            return
        await self._client.set(self._key(key), json.dumps(value, separators=(",", ":")), ex=ttl)

    async def delete(self, key: str) -> None:
        await self._client.delete(self._key(key))

    async def clear(self) -> None:
        keys: list[str] = []
        async for raw_key in self._client.scan_iter(match=self._key("*")):
            keys.append(raw_key.decode("utf-8") if isinstance(raw_key, bytes) else raw_key)
            if len(keys) == 500:
                await self._client.delete(*keys)
                keys.clear()
        if keys:
            await self._client.delete(*keys)

    async def close(self) -> None:
        await self._client.aclose()


__all__ = ["RedisCache", "RedisClient"]
