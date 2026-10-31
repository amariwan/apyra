"""Optional Taskiq integration for Apyra tasks."""

from __future__ import annotations

from collections.abc import Callable
from importlib import import_module
from typing import Any, TypeVar

F = TypeVar("F", bound=Callable[..., Any])


class TaskiqUnavailableError(RuntimeError):
    """Raised when Taskiq is not installed."""


class TaskiqAdapter:
    """Small adapter around a Taskiq broker.

    The adapter keeps Taskiq optional. It only imports Taskiq when a broker is
    actually required, and accepts an injected broker for tests.
    """

    def __init__(
        self,
        broker: Any | None = None,
        *,
        default_retries: int = 0,
        default_timeout: float | None = None,
    ) -> None:
        self._broker = broker
        self._default_retries = default_retries
        self._default_timeout = default_timeout

    def _resolve_broker(self) -> Any:
        if self._broker is not None:
            return self._broker
        try:
            taskiq = import_module("taskiq")
        except ModuleNotFoundError as exc:
            if exc.name != "taskiq":
                raise
            raise TaskiqUnavailableError(
                "Taskiq is not installed; install apyra-tasks[taskiq]"
            ) from exc
        self._broker = taskiq.InMemoryBroker()
        return self._broker

    def task(
        self,
        func: Any = None,
        *,
        retries: int | None = None,
        timeout: float | None = None,
    ) -> Any:
        """Decorate a callable with Taskiq retry and timeout options."""
        broker = self._resolve_broker()
        resolved_retries = self._default_retries if retries is None else retries
        resolved_timeout = self._default_timeout if timeout is None else timeout
        decorator = broker.task(
            retry_on_error=resolved_retries > 0,
            max_retries=resolved_retries,
            timeout=resolved_timeout,
        )
        if func is not None:
            return decorator(func)
        return decorator

    async def run(self, task: Any, *args: Any, **kwargs: Any) -> Any:
        """Run or enqueue a Taskiq task and return its resolved result."""
        if hasattr(task, "kiq"):
            task_result = await task.kiq(*args, **kwargs)
            if hasattr(task_result, "wait_result"):
                result = await task_result.wait_result()
                return getattr(result, "return_value", result)
        if callable(task):
            return await _maybe_await(task(*args, **kwargs))
        raise TypeError("Taskiq task must be callable")


async def _maybe_await(value: Any) -> Any:
    if hasattr(value, "__await__"):
        return await value
    return value
