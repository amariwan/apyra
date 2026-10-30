"""In-memory cache with TTL."""

from __future__ import annotations

import time


class InMemoryCache:
    def __init__(self) -> None:
        self._data: dict[str, tuple[object, float | None]] = {}

    async def get(self, key: str) -> object | None:
        item = self._data.get(key)
        if item is None:
            return None
        value, expires_at = item
        if expires_at is not None and expires_at <= time.monotonic():
            del self._data[key]
            return None
        return value

    async def set(self, key: str, value: object, *, ttl_seconds: int | None = None) -> None:
        expires_at = None if ttl_seconds is None else time.monotonic() + ttl_seconds
        self._data[key] = (value, expires_at)

    async def delete(self, key: str) -> None:
        self._data.pop(key, None)
