"""Simple async task runner with retries and timeouts."""

from __future__ import annotations

import asyncio

from .tasks import Task, TaskResult


class TaskRunner:
    def __init__(self) -> None:
        self._tasks: dict[str, Task] = {}

    def register(self, task: Task) -> None:
        self._tasks[task.name] = task

    async def run(self, name: str) -> TaskResult:
        task = self._tasks[name]
        attempts = 0
        last_error: str | None = None
        for attempt in range(1, task.max_attempts + 1):
            attempts = attempt
            try:
                coroutine = task.func()
                if task.timeout_seconds is not None:
                    await asyncio.wait_for(coroutine, timeout=task.timeout_seconds)
                else:
                    await coroutine
                return TaskResult(name=name, success=True, attempts=attempts)
            except Exception as exc:  # noqa: BLE001
                last_error = str(exc)
        return TaskResult(name=name, success=False, attempts=attempts, error=last_error)
