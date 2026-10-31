"""Optional Celery integration for Apyra tasks."""

from __future__ import annotations

from collections.abc import Callable
from importlib import import_module
from typing import Any

F = Callable[..., Any]


class CeleryUnavailableError(RuntimeError):
    """Raised when Celery is not installed."""


class CeleryAdapter:
    """Small adapter around a Celery application."""

    def __init__(
        self,
        app: Any | None = None,
        *,
        broker_url: str | None = None,
        default_retries: int = 0,
        default_timeout: float | None = None,
    ) -> None:
        self._app = app
        self._broker_url = broker_url
        self._default_retries = default_retries
        self._default_timeout = default_timeout

    def _resolve_app(self) -> Any:
        if self._app is not None:
            return self._app
        try:
            celery = import_module("celery")
        except ModuleNotFoundError as exc:
            if exc.name != "celery":
                raise
            raise CeleryUnavailableError(
                "Celery is not installed; install apyra-tasks[celery]"
            ) from exc
        self._app = celery.Celery("apyra", broker=self._broker_url)
        return self._app

    def task(
        self,
        func: F | None = None,
        *,
        retries: int | None = None,
        timeout: float | None = None,
    ) -> Any:
        """Decorate a callable with Celery retry and soft/hard timeout options."""
        app = self._resolve_app()
        resolved_retries = self._default_retries if retries is None else retries
        resolved_timeout = self._default_timeout if timeout is None else timeout
        options: dict[str, Any] = {"max_retries": resolved_retries}
        if resolved_retries > 0:
            options["autoretry_for"] = (Exception,)
        if resolved_timeout is not None:
            options["soft_time_limit"] = resolved_timeout
            options["time_limit"] = resolved_timeout
        decorator = app.task(**options)
        if func is not None:
            return decorator(func)
        return decorator

    def send(self, task: Any, *args: Any, **kwargs: Any) -> Any:
        """Enqueue a decorated task through Celery's ``delay`` interface."""
        return task.delay(*args, **kwargs)
