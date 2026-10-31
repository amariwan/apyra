import asyncio
import math
import threading
from collections.abc import Awaitable, Callable
from typing import cast

import pytest

from apyra.tasks import repeat_every


@pytest.mark.asyncio
async def test_repeat_every_preserves_none_return_by_default() -> None:
    completed = asyncio.Event()

    @repeat_every(seconds=0.01, max_repetitions=1)
    async def task() -> None:
        completed.set()

    starter = cast(Callable[[], Awaitable[object]], task)
    result = await starter()
    await asyncio.wait_for(completed.wait(), timeout=1)
    assert result is None


@pytest.mark.parametrize("seconds", [math.nan, math.inf, -math.inf])
def test_repeat_every_rejects_non_finite_interval(seconds: float) -> None:
    with pytest.raises(ValueError, match="finite.*greater than zero"):
        repeat_every(seconds=seconds)


@pytest.mark.parametrize("wait_first", [math.nan, math.inf, -math.inf])
def test_repeat_every_rejects_non_finite_initial_delay(wait_first: float) -> None:
    with pytest.raises(ValueError, match="finite"):
        repeat_every(seconds=1, wait_first=wait_first)


@pytest.mark.asyncio
async def test_repeat_every_runs_limited_repetitions() -> None:
    calls: list[int] = []

    @repeat_every(seconds=0.01, max_repetitions=3, return_task_handle=True)
    async def task() -> None:
        calls.append(len(calls) + 1)

    handle = await task()
    await handle
    assert calls == [1, 2, 3]


@pytest.mark.asyncio
async def test_repeat_every_handles_exceptions() -> None:
    calls: list[int] = []
    errors: list[str] = []

    @repeat_every(
        seconds=0.01,
        max_repetitions=2,
        on_exception=lambda exc: errors.append(str(exc)),
        return_task_handle=True,
    )
    async def task() -> None:
        calls.append(len(calls) + 1)
        raise RuntimeError("boom")

    handle = await task()
    await handle
    assert calls == [1, 2]
    assert errors == ["boom", "boom"]


@pytest.mark.asyncio
async def test_repeat_every_returns_cancellable_background_task() -> None:
    started = asyncio.Event()

    @repeat_every(seconds=1, return_task_handle=True)
    async def task() -> None:
        started.set()

    handle = await task()
    await asyncio.wait_for(started.wait(), timeout=1)
    handle.cancel()

    with pytest.raises(asyncio.CancelledError):
        await handle


@pytest.mark.asyncio
async def test_repeat_every_accepts_runtime_boolean_handle_option() -> None:
    return_handle: bool = True

    @repeat_every(seconds=0.01, max_repetitions=1, return_task_handle=return_handle)
    async def task() -> None:
        return None

    handle = await task()
    assert isinstance(handle, asyncio.Task)
    await handle


@pytest.mark.asyncio
async def test_repeat_every_offloads_sync_functions() -> None:
    caller_thread = threading.get_ident()
    worker_threads: list[int] = []

    @repeat_every(seconds=0.01, max_repetitions=1, return_task_handle=True)
    def task() -> None:
        worker_threads.append(threading.get_ident())

    handle = await task()
    await handle
    assert len(worker_threads) == 1
    assert worker_threads[0] != caller_thread


@pytest.mark.asyncio
async def test_repeat_every_offloads_sync_exception_and_completion_handlers() -> None:
    caller_thread = threading.get_ident()
    callback_threads: list[int] = []

    def on_exception(_exc: Exception) -> None:
        callback_threads.append(threading.get_ident())

    def on_complete() -> None:
        callback_threads.append(threading.get_ident())

    @repeat_every(
        seconds=0.01,
        max_repetitions=1,
        on_exception=on_exception,
        on_complete=on_complete,
        return_task_handle=True,
    )
    def task() -> None:
        raise RuntimeError("expected")

    handle = await task()
    await handle
    assert len(callback_threads) == 2
    assert all(thread_id != caller_thread for thread_id in callback_threads)


@pytest.mark.asyncio
async def test_cancel_does_not_interrupt_an_inflight_sync_callback() -> None:
    started = threading.Event()
    release = threading.Event()
    finished = threading.Event()

    @repeat_every(seconds=1, return_task_handle=True)
    def task() -> None:
        started.set()
        release.wait()
        finished.set()

    handle = await task()
    try:
        assert await asyncio.to_thread(started.wait, 1)
        handle.cancel()
        with pytest.raises(asyncio.CancelledError):
            await handle
        assert not finished.is_set()
    finally:
        release.set()
        assert await asyncio.to_thread(finished.wait, 1)
