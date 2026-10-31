import builtins
from collections.abc import Awaitable, Callable
from types import SimpleNamespace
from typing import Any

import pytest

from apyra.tasks import TaskiqAdapter, TaskiqUnavailableError


class FakeTask:
    def __init__(self, func: Callable[..., Awaitable[Any]]) -> None:
        self.func = func
        self.calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    async def __call__(self, *args: Any, **kwargs: Any) -> Any:
        self.calls.append((args, kwargs))
        return await self.func(*args, **kwargs)


class FakeBroker:
    def __init__(self) -> None:
        self.registered: list[Any] = []

    def task(self, *, retry_on_error: bool, max_retries: int, timeout: float | None):
        def decorator(func: Callable[..., Awaitable[Any]]) -> FakeTask:
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
    original_import = builtins.__import__

    def import_without_taskiq(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "taskiq":
            raise ModuleNotFoundError("No module named 'taskiq'", name="taskiq")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", import_without_taskiq)
    adapter = TaskiqAdapter()
    with pytest.raises(TaskiqUnavailableError):
        adapter.task(lambda: None)


def test_taskiq_adapter_does_not_mask_internal_import_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_import = builtins.__import__

    def broken_taskiq(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "taskiq":
            raise ImportError("taskiq has a broken internal dependency")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", broken_taskiq)
    with pytest.raises(ImportError, match="broken internal dependency"):
        TaskiqAdapter().task(lambda: None)


def test_taskiq_adapter_does_not_mask_missing_internal_modules(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_import = builtins.__import__

    def broken_taskiq(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "taskiq":
            raise ModuleNotFoundError("No module named 'taskiq.backend'", name="taskiq.backend")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", broken_taskiq)
    with pytest.raises(ModuleNotFoundError, match="taskiq.backend"):
        TaskiqAdapter().task(lambda: None)


def test_taskiq_adapter_task_factory_accepts_explicit_options() -> None:
    broker = FakeBroker()
    adapter = TaskiqAdapter(broker=broker)
    decorate = adapter.task(retries=3, timeout=2.5)

    @decorate
    async def work() -> str:
        return "done"

    assert broker.registered[0][1:] == (True, 3, 2.5)
    assert work is broker.registered[0][0]


@pytest.mark.asyncio
async def test_taskiq_adapter_resolves_enqueued_result() -> None:
    async def wait_result() -> object:
        return SimpleNamespace(return_value=42)

    class EnqueuedTaskWithAsyncResult:
        async def kiq(self) -> object:
            return SimpleNamespace(wait_result=wait_result)

    adapter = TaskiqAdapter(broker=object())
    assert await adapter.run(EnqueuedTaskWithAsyncResult()) == 42


@pytest.mark.asyncio
async def test_taskiq_adapter_runs_sync_callables_and_rejects_invalid_tasks() -> None:
    adapter = TaskiqAdapter(broker=object())

    def increment(value: int) -> int:
        return value + 1

    assert await adapter.run(increment, 4) == 5

    with pytest.raises(TypeError, match="must be callable"):
        await adapter.run(object())


def test_taskiq_adapter_resolves_installed_inmemory_broker() -> None:
    pytest.importorskip("taskiq")
    adapter = TaskiqAdapter()

    async def work() -> None:
        return None

    registered = adapter.task(work)
    assert hasattr(registered, "kiq")
