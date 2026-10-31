"""Cache protocol."""

from __future__ import annotations

from typing import Protocol


class CacheClient(Protocol):
    """Minimal async cache interface consumed by ``CacheManager``."""

    async def get(self, key: str) -> object | None:
        """Return the value for a key, or ``None`` when absent."""
        ...

    async def set(self, key: str, value: object, *, ttl_seconds: int | None = None) -> None:
        """Store a value with an optional expiration in seconds."""
        ...

    async def delete(self, key: str) -> None:
        """Remove one key if it exists."""
        ...
