"""Cache protocol."""

from __future__ import annotations

from typing import Protocol


class CacheClient(Protocol):
    async def get(self, key: str) -> object | None: ...
    async def set(self, key: str, value: object, *, ttl_seconds: int | None = None) -> None: ...
    async def delete(self, key: str) -> None: ...
