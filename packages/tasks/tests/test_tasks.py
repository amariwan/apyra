import asyncio
from collections.abc import Awaitable
from math import inf, nan

import pytest

from apyra.tasks import Task, TaskResult, TaskRunner


@pytest.mark.parametrize("max_attempts", [0, -1, True, 1.5])
def test_task_rejects_invalid_attempt_count(max_attempts: int) -> None:
    async def run() -> None:
        return None

    with pytest.raises(ValueError, match="max_attempts must be a positive integer"):
        Task(name="invalid", func=run, max_attempts=max_attempts)


@pytest.mark.parametrize("timeout_seconds", [0, -1, inf, -inf, nan, True])
def test_task_rejects_invalid_timeout(timeout_seconds: float) -> None:
    async def run() -> None:
        return None

    with pytest.raises(ValueError, match="timeout_seconds must be finite and greater than zero"):
        Task(name="invalid", func=run, timeout_seconds=timeout_seconds)


@pytest.mark.asyncio
async def test_task_runner_retries_and_succeeds() -> None:
    attempts = {"count": 0}

    async def flaky() -> None:
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise RuntimeError("boom")

    runner = TaskRunner()
    runner.register(Task(name="flaky", func=flaky, max_attempts=2))
    result = await runner.run("flaky")
    assert result == TaskResult(name="flaky", success=True, attempts=2)


@pytest.mark.asyncio
async def test_task_runner_retries_synchronous_task_creation_failure() -> None:
    calls = 0

    def flaky() -> Awaitable[None]:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("creation failed")

        async def succeed() -> None:
            return None

        return succeed()

    runner = TaskRunner()
    runner.register(Task(name="flaky", func=flaky, max_attempts=2))

    result = await runner.run("flaky")

    assert result == TaskResult(name="flaky", success=True, attempts=2)


@pytest.mark.asyncio
async def test_task_runner_timeout() -> None:
    async def slow() -> None:
        await asyncio.sleep(1)

    runner = TaskRunner()
    runner.register(Task(name="slow", func=slow, max_attempts=1, timeout_seconds=0.01))
    result = await runner.run("slow")
    assert not result.success
    assert result.error is not None
