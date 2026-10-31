"""Provider-neutral publish/subscribe channel contract."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Protocol


class ChannelSubscription(Protocol):
    """Async iterator for messages received from one subscribed channel."""

    def __aiter__(self) -> AsyncIterator[Any]:
        """Return the subscription's asynchronous message iterator."""
        ...

    async def __anext__(self) -> Any:
        """Return the next message, raising ``StopAsyncIteration`` when closed."""
        ...

    async def close(self) -> None:
        """Stop message delivery and release provider resources."""
        ...


class ChannelLayer(Protocol):
    """Provider-neutral publish/subscribe contract for realtime messages."""

    async def publish(self, channel: str, message: Any) -> int:
        """Publish a message and return the number of delivered subscribers."""
        ...

    async def subscribe(self, channel: str) -> ChannelSubscription:
        """Subscribe to a channel and return its async message stream."""
        ...

    async def close(self) -> None:
        """Stop the layer and release provider resources."""
        ...


__all__ = ["ChannelLayer", "ChannelSubscription"]
