from typing import Any

import pytest

from apyra.tasks import TaskiqAdapter, TaskiqUnavailableError


class FakeTask:
    def __init__(self, func):
        self.func = func
        self.calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    async def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return await self.func(*args, **kwargs)


class FakeBroker:
    def __init__(self) -> None:
        self.registered: list[Any] = []

    def task(self, *, retry_on_error: bool, max_retries: int, timeout: float | None):
        def decorator(func):
            task = FakeTask(func)
            self.registered.append((task, retry_on_error, max_retries, timeout))
            return task

        return decorator


@pytest.mark.asyncio
async def test_taskiq_adapter_registers_and_runs_task() -> None:
    broker = FakeBroker()
    adapter = TaskiqAdapter(broker=broker, default_retries=2, default_timeout=5)

    @adapter.task
    async def add(a: int, b: int) -> int:
        return a + b

    assert broker.registered[0][1:] == (True, 2, 5)
    assert await adapter.run(add, 2, 3) == 5
    assert add.calls == [((2, 3), {})]


def test_taskiq_adapter_unavailable_without_dependency(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(__import__("sys").modules, "taskiq.brokers.inmemory", None)
    adapter = TaskiqAdapter()
    with pytest.raises(TaskiqUnavailableError):
        adapter.task(lambda: None)
