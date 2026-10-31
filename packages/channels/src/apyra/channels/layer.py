"""Provider-neutral publish/subscribe channel contract."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Protocol


class ChannelSubscription(Protocol):
    def __aiter__(self) -> AsyncIterator[Any]: ...

    async def __anext__(self) -> Any: ...

    async def close(self) -> None: ...


class ChannelLayer(Protocol):
    async def publish(self, channel: str, message: Any) -> int: ...

    async def subscribe(self, channel: str) -> ChannelSubscription: ...

    async def close(self) -> None: ...


__all__ = ["ChannelLayer", "ChannelSubscription"]
