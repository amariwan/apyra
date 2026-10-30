"""Periodic task helpers."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from functools import wraps

NoArgsFunc = Callable[[], Awaitable[None] | None]
ExceptionHandler = Callable[[Exception], Awaitable[None] | None]


def repeat_every(
    *,
    seconds: float,
    wait_first: float | None = None,
    max_repetitions: int | None = None,
    on_complete: NoArgsFunc | None = None,
    on_exception: ExceptionHandler | None = None,
) -> Callable[[NoArgsFunc], Callable[[], Awaitable[None]]]:
    """Decorate a no-argument function so it runs repeatedly."""

    if seconds <= 0:
        raise ValueError("seconds must be greater than zero")

    def decorator(func: NoArgsFunc) -> Callable[[], Awaitable[None]]:
        @wraps(func)
        async def wrapped() -> None:
            async def loop() -> None:
                if wait_first is not None:
                    await asyncio.sleep(wait_first)

                repetitions = 0
                while max_repetitions is None or repetitions < max_repetitions:
                    try:
                        result = func()
                        if hasattr(result, "__await__"):
                            await result  # type: ignore[misc]
                    except Exception as exc:
                        if on_exception is not None:
                            result = on_exception(exc)
                            if hasattr(result, "__await__"):
                                await result  # type: ignore[misc]
                        else:
                            logging.getLogger(__name__).exception("Repeated task failed")
                    repetitions += 1
                    if max_repetitions is None or repetitions < max_repetitions:
                        await asyncio.sleep(seconds)

                if on_complete is not None:
                    result = on_complete()
                    if hasattr(result, "__await__"):
                        await result  # type: ignore[misc]

            asyncio.create_task(loop())

        return wrapped

    return decorator
