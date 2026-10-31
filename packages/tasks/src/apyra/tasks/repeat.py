"""Periodic task helpers."""

from __future__ import annotations

import asyncio
import inspect
import logging
import math
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Any, Literal, cast, overload

NoArgsFunc = Callable[[], Awaitable[None] | None]
ExceptionHandler = Callable[[Exception], Awaitable[None] | None]


async def _run_callback(callback: Callable[..., Awaitable[None] | None], *args: object) -> None:
    if inspect.iscoroutinefunction(callback):
        result = callback(*args)
    else:
        result = await asyncio.to_thread(cast(Callable[..., Any], callback), *args)
    if inspect.isawaitable(result):
        await result


@overload
def repeat_every(
    *,
    seconds: float,
    wait_first: float | None = None,
    max_repetitions: int | None = None,
    on_complete: NoArgsFunc | None = None,
    on_exception: ExceptionHandler | None = None,
    return_task_handle: Literal[True],
) -> Callable[[NoArgsFunc], Callable[[], Awaitable[asyncio.Task[None]]]]: ...


@overload
def repeat_every(
    *,
    seconds: float,
    wait_first: float | None = None,
    max_repetitions: int | None = None,
    on_complete: NoArgsFunc | None = None,
    on_exception: ExceptionHandler | None = None,
    return_task_handle: Literal[False] = False,
) -> Callable[[NoArgsFunc], Callable[[], Awaitable[None]]]: ...


@overload
def repeat_every(
    *,
    seconds: float,
    wait_first: float | None = None,
    max_repetitions: int | None = None,
    on_complete: NoArgsFunc | None = None,
    on_exception: ExceptionHandler | None = None,
    return_task_handle: bool,
) -> Callable[[NoArgsFunc], Callable[[], Awaitable[asyncio.Task[None] | None]]]: ...


def repeat_every(
    *,
    seconds: float,
    wait_first: float | None = None,
    max_repetitions: int | None = None,
    on_complete: NoArgsFunc | None = None,
    on_exception: ExceptionHandler | None = None,
    return_task_handle: bool = False,
) -> Callable[[NoArgsFunc], Callable[[], Awaitable[asyncio.Task[None] | None]]]:
    """Decorate a periodic function; optionally return its cancellable task handle."""

    if not math.isfinite(seconds) or seconds <= 0:
        raise ValueError("seconds must be finite and greater than zero")
    if wait_first is not None and not math.isfinite(wait_first):
        raise ValueError("wait_first must be finite")

    def decorator(func: NoArgsFunc) -> Callable[[], Awaitable[asyncio.Task[None] | None]]:
        @wraps(func)
        async def wrapped() -> asyncio.Task[None] | None:
            async def loop() -> None:
                if wait_first is not None:
                    await asyncio.sleep(wait_first)

                repetitions = 0
                while max_repetitions is None or repetitions < max_repetitions:
                    try:
                        await _run_callback(func)
                    except Exception as exc:
                        if on_exception is not None:
                            await _run_callback(on_exception, exc)
                        else:
                            logging.getLogger(__name__).exception("Repeated task failed")
                    repetitions += 1
                    if max_repetitions is None or repetitions < max_repetitions:
                        await asyncio.sleep(seconds)

                if on_complete is not None:
                    await _run_callback(on_complete)

            task = asyncio.create_task(loop(), name=f"apyra.repeat_every:{func.__qualname__}")
            return task if return_task_handle else None

        return wrapped

    return decorator
