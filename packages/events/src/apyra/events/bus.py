"""In-process asynchronous event bus."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Awaitable, Callable

from .events import Event

Handler = Callable[[Event], Awaitable[None] | None]


class EventBus:
    async def publish(self, event: Event) -> list[BaseException]:
        raise NotImplementedError

    def subscribe(self, event_name: str, handler: Handler) -> None:
        raise NotImplementedError


class InMemoryEventBus(EventBus):
    def __init__(self, *, max_concurrency: int = 10) -> None:
        self._handlers: dict[str, list[Handler]] = defaultdict(list)
        self._semaphore = asyncio.Semaphore(max_concurrency)

    def subscribe(self, event_name: str, handler: Handler) -> None:
        self._handlers[event_name].append(handler)

    def unsubscribe(self, event_name: str, handler: Handler) -> None:
        self._handlers[event_name] = [
            item for item in self._handlers[event_name] if item is not handler
        ]

    async def publish(self, event: Event) -> list[BaseException]:
        errors: list[BaseException] = []
        handlers = list(self._handlers.get(event.name, ()))

        async def run(handler: Handler) -> None:
            async with self._semaphore:
                result = handler(event)
                if hasattr(result, "__await__"):
                    await result  # type: ignore[misc]

        results = await asyncio.gather(
            *(run(handler) for handler in handlers), return_exceptions=True
        )
        for result in results:
            if isinstance(result, BaseException):
                errors.append(result)
        return errors
