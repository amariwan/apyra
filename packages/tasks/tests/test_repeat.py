import asyncio

import pytest

from apyra.tasks import repeat_every


@pytest.mark.asyncio
async def test_repeat_every_runs_limited_repetitions() -> None:
    calls: list[int] = []

    @repeat_every(seconds=0.01, max_repetitions=3)
    async def task() -> None:
        calls.append(len(calls) + 1)

    await task()
    await asyncio.sleep(0.1)
    assert calls == [1, 2, 3]


@pytest.mark.asyncio
async def test_repeat_every_handles_exceptions() -> None:
    calls: list[int] = []
    errors: list[str] = []

    @repeat_every(seconds=0.01, max_repetitions=2, on_exception=lambda exc: errors.append(str(exc)))
    async def task() -> None:
        calls.append(len(calls) + 1)
        raise RuntimeError("boom")

    await task()
    await asyncio.sleep(0.1)
    assert calls == [1, 2]
    assert errors == ["boom", "boom"]
