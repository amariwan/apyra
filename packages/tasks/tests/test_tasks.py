import asyncio

import pytest

from apyra.tasks import Task, TaskResult, TaskRunner


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
async def test_task_runner_timeout() -> None:
    async def slow() -> None:
        await asyncio.sleep(1)

    runner = TaskRunner()
    runner.register(Task(name="slow", func=slow, max_attempts=1, timeout_seconds=0.01))
    result = await runner.run("slow")
    assert not result.success
    assert result.error is not None
