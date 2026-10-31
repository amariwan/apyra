"""Shared event-handler invocation behavior for event bus implementations."""

from __future__ import annotations

import asyncio
import inspect
import logging
from collections.abc import Awaitable, Callable

from .events import Event

Handler = Callable[[Event], Awaitable[None] | None]
logger: logging.Logger = logging.getLogger("apyra.events")


async def invoke_handler(handler: Handler, event: Event) -> None:
    """Invoke async handlers directly and sync handlers off-loop.

    Cancellation waits for in-flight synchronous work because worker threads cannot
    be stopped safely; handlers should use bounded I/O and cooperative timeouts.
    """
    if inspect.iscoroutinefunction(handler):
        await handler(event)
        return

    worker = asyncio.create_task(asyncio.to_thread(handler, event))
    try:
        result = await asyncio.shield(worker)
    except asyncio.CancelledError:
        while True:
            try:
                await asyncio.shield(worker)
            except asyncio.CancelledError:
                if worker.done():
                    break
                continue
            except Exception:
                logger.exception("Synchronous event handler failed during cancellation")
                break
            break
        raise
    if inspect.isawaitable(result):
        await result
