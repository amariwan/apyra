"""In-process asynchronous event bus."""

from __future__ import annotations

import asyncio
import warnings
from collections import defaultdict
from typing import Any

from .dispatch import Handler, invoke_handler
from .events import Event


class EventBus:
    """Asynchronous event publication and subscription contract."""

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        missing = [
            name
            for name in ("publish", "subscribe")
            if getattr(cls, name) is getattr(EventBus, name)
        ]
        if missing:
            methods = ", ".join(f"{name}()" for name in missing)
            warnings.warn(
                f"{cls.__name__} must implement {methods}; abstract enforcement is deprecated "
                "and will begin no earlier than the next major apyra-events release",
                DeprecationWarning,
                stacklevel=2,
            )

    async def publish(self, event: Event) -> list[BaseException]:
        """Publish an event and return handler failures."""
        raise NotImplementedError(f"{type(self).__name__} must implement publish()")

    def subscribe(self, event_name: str, handler: Handler) -> None:
        """Register a handler for an event name."""
        raise NotImplementedError(f"{type(self).__name__} must implement subscribe()")


class InMemoryEventBus(EventBus):
    """Concurrent in-process event bus that collects handler failures."""

    def __init__(self, *, max_concurrency: int = 10) -> None:
        """Create a bus limiting simultaneous handler execution."""
        if max_concurrency < 1:
            raise ValueError("max_concurrency must be positive")
        self._handlers: dict[str, list[Handler]] = defaultdict(list)
        self._semaphore = asyncio.Semaphore(max_concurrency)

    def subscribe(self, event_name: str, handler: Handler) -> None:
        """Register a synchronous or asynchronous handler for one event name."""
        self._handlers[event_name].append(handler)

    def unsubscribe(self, event_name: str, handler: Handler) -> None:
        """Remove registrations of this exact handler for the event name."""
        self._handlers[event_name] = [
            item for item in self._handlers[event_name] if item is not handler
        ]

    async def publish(self, event: Event) -> list[BaseException]:
        """Dispatch to current handlers and return their failures without raising them."""
        errors: list[BaseException] = []
        handlers = list(self._handlers.get(event.name, ()))

        async def run(handler: Handler) -> None:
            async with self._semaphore:
                await invoke_handler(handler, event)

        results = await asyncio.gather(
            *(run(handler) for handler in handlers), return_exceptions=True
        )
        for result in results:
            if isinstance(result, BaseException):
                errors.append(result)
        return errors
