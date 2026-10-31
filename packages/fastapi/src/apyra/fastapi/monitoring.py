"""Error and performance monitoring middleware for Apyra FastAPI applications."""

from __future__ import annotations

import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, cast

from apyra.observability import (
    PerformanceMonitor,
    capture_exception,
    get_performance_monitor,
)
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


@dataclass(frozen=True)
class ErrorMonitoringConfig:
    """Configuration for :class:`ErrorMonitoringMiddleware`."""

    reraise: bool = True
    level: str = "error"
    tags: Mapping[str, str] = field(default_factory=lambda: dict[str, str]())
    exclude_paths: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        allowed = {"debug", "info", "warning", "error", "critical"}
        if self.level.lower() not in allowed:
            raise ValueError(f"level must be one of {sorted(allowed)}")


@dataclass(frozen=True)
class PerformanceMonitoringConfig:
    """Configuration for :class:`PerformanceMonitoringMiddleware`."""

    header_name: str = "X-Response-Time"
    record: bool = True
    monitor: PerformanceMonitor | None = None
    metric_name: str = "http.request"
    exclude_paths: tuple[str, ...] = ()
    tags: Mapping[str, str] = field(default_factory=lambda: dict[str, str]())

    def __post_init__(self) -> None:
        if not self.header_name:
            raise ValueError("header_name must not be empty")
        if not self.metric_name:
            raise ValueError("metric_name must not be empty")


class ErrorMonitoringMiddleware(BaseHTTPMiddleware):
    """Capture unhandled exceptions and optionally convert them to HTTP 500."""

    def __init__(
        self,
        app: Any,
        *,
        config: ErrorMonitoringConfig | None = None,
        reraise: bool = True,
        level: str = "error",
        tags: Mapping[str, str] | None = None,
        exclude_paths: Sequence[str] = (),
    ) -> None:
        super().__init__(app)
        resolved = config or ErrorMonitoringConfig(
            reraise=reraise,
            level=level,
            tags=dict(tags or {}),
            exclude_paths=tuple(exclude_paths),
        )
        self._config = resolved

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        if request.url.path in self._config.exclude_paths:
            return cast(Response, await call_next(request))
        try:
            response = await call_next(request)
            return cast(Response, response)
        except Exception as exc:
            capture_exception(
                exc,
                level=self._config.level,
                tags=self._config.tags,
                context={
                    "method": request.method,
                    "path": request.url.path,
                },
            )
            if self._config.reraise:
                raise
            return JSONResponse(status_code=500, content={"detail": "internal server error"})


class PerformanceMonitoringMiddleware(BaseHTTPMiddleware):
    """Record request durations and add a response timing header."""

    def __init__(
        self,
        app: Any,
        *,
        config: PerformanceMonitoringConfig | None = None,
        header_name: str = "X-Response-Time",
        record: bool = True,
        monitor: PerformanceMonitor | None = None,
        metric_name: str = "http.request",
        exclude_paths: Sequence[str] = (),
        tags: Mapping[str, str] | None = None,
    ) -> None:
        super().__init__(app)
        resolved = config or PerformanceMonitoringConfig(
            header_name=header_name,
            record=record,
            monitor=monitor,
            metric_name=metric_name,
            exclude_paths=tuple(exclude_paths),
            tags=dict(tags or {}),
        )
        self._config = resolved

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        if request.url.path in self._config.exclude_paths:
            return cast(Response, await call_next(request))

        started_at = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            elapsed_seconds = time.perf_counter() - started_at
            if self._config.record:
                target = self._config.monitor or get_performance_monitor()
                target.record(
                    self._config.metric_name,
                    elapsed_seconds,
                    tags={
                        "path": request.url.path,
                        "method": request.method,
                        "status_code": "exception",
                        **dict(self._config.tags),
                    },
                )
            raise
        typed_response = cast(Response, response)
        elapsed_seconds = time.perf_counter() - started_at
        typed_response.headers[self._config.header_name] = f"{elapsed_seconds * 1000:.2f}ms"

        if self._config.record:
            target = self._config.monitor or get_performance_monitor()
            target.record(
                self._config.metric_name,
                elapsed_seconds,
                tags={
                    "path": request.url.path,
                    "method": request.method,
                    "status_code": str(typed_response.status_code),
                    **dict(self._config.tags),
                },
            )
        return typed_response


# Aliases for naming flexibility.
ErrorMiddleware = ErrorMonitoringMiddleware
PerformanceMiddleware = PerformanceMonitoringMiddleware
MonitoringMiddleware = PerformanceMonitoringMiddleware


def _validate_kwargs(kwargs: dict[str, Any], allowed: set[str], function_name: str) -> None:
    unknown = set(kwargs) - allowed
    if unknown:
        raise TypeError(f"{function_name}() got unexpected keyword arguments: {sorted(unknown)}")


def register_error_monitoring_middleware(
    app: Any,
    *,
    config: ErrorMonitoringConfig | None = None,
    **kwargs: Any,
) -> None:
    """Register :class:`ErrorMonitoringMiddleware` on an app."""
    if config is not None and kwargs:
        raise TypeError("Pass either config or keyword arguments, not both")
    if config is None:
        _validate_kwargs(
            kwargs,
            {"reraise", "level", "tags", "exclude_paths"},
            "register_error_monitoring_middleware",
        )
        config = ErrorMonitoringConfig(**kwargs)
    app.add_middleware(ErrorMonitoringMiddleware, config=config)


def register_performance_monitoring_middleware(
    app: Any,
    *,
    config: PerformanceMonitoringConfig | None = None,
    **kwargs: Any,
) -> None:
    """Register :class:`PerformanceMonitoringMiddleware` on an app."""
    if config is not None and kwargs:
        raise TypeError("Pass either config or keyword arguments, not both")
    if config is None:
        _validate_kwargs(
            kwargs,
            {"header_name", "record", "monitor", "metric_name", "exclude_paths", "tags"},
            "register_performance_monitoring_middleware",
        )
        config = PerformanceMonitoringConfig(**kwargs)
    app.add_middleware(PerformanceMonitoringMiddleware, config=config)


def register_monitoring_middleware(
    app: Any,
    *,
    error: bool = True,
    performance: bool = True,
    error_config: ErrorMonitoringConfig | None = None,
    performance_config: PerformanceMonitoringConfig | None = None,
    **kwargs: Any,
) -> None:
    """Register error and/or performance monitoring middleware.

    Shared ``tags`` and ``exclude_paths`` keyword arguments are applied to both
    middlewares. Use ``error_<name>`` or ``performance_<name>`` prefixes for
    middleware-specific values.
    """
    error_allowed = {"reraise", "level", "tags", "exclude_paths"}
    performance_allowed = {
        "header_name",
        "record",
        "monitor",
        "metric_name",
        "tags",
        "exclude_paths",
    }

    error_kwargs: dict[str, Any] = {}
    performance_kwargs: dict[str, Any] = {}
    unknown: list[str] = []
    shared_tags: dict[str, str] = {}
    shared_exclude: tuple[str, ...] | None = None

    for key, value in kwargs.items():
        if key.startswith("error_"):
            target_key = key[len("error_") :]
            if target_key not in error_allowed:
                unknown.append(key)
                continue
            error_kwargs[target_key] = value
        elif key.startswith("performance_"):
            target_key = key[len("performance_") :]
            if target_key not in performance_allowed:
                unknown.append(key)
                continue
            performance_kwargs[target_key] = value
        elif key in {"tags", "exclude_paths"}:
            if key == "tags":
                shared_tags.update(value or {})
            else:
                shared_exclude = tuple(value)
        elif key in error_allowed or key in performance_allowed:
            if key in error_allowed:
                error_kwargs[key] = value
            if key in performance_allowed:
                performance_kwargs[key] = value
        else:
            unknown.append(key)

    if unknown:
        raise TypeError(
            "register_monitoring_middleware() got unexpected keyword arguments: "
            + str(sorted(unknown))
        )

    if "tags" in shared_tags or shared_tags:
        error_kwargs.setdefault("tags", {}).update(shared_tags)
        performance_kwargs.setdefault("tags", {}).update(shared_tags)
    if shared_exclude is not None:
        error_kwargs.setdefault("exclude_paths", shared_exclude)
        performance_kwargs.setdefault("exclude_paths", shared_exclude)

    if error:
        if error_config is not None and error_kwargs:
            raise TypeError("Pass either error_config or error keyword arguments, not both")
        if error_config is not None:
            register_error_monitoring_middleware(app, config=error_config)
        elif error_kwargs:
            register_error_monitoring_middleware(app, **error_kwargs)
        else:
            register_error_monitoring_middleware(app)

    if performance:
        if performance_config is not None and performance_kwargs:
            raise TypeError(
                "Pass either performance_config or performance keyword arguments, not both"
            )
        if performance_config is not None:
            register_performance_monitoring_middleware(app, config=performance_config)
        elif performance_kwargs:
            register_performance_monitoring_middleware(app, **performance_kwargs)
        else:
            register_performance_monitoring_middleware(app)


__all__ = [
    "ErrorMiddleware",
    "ErrorMonitoringConfig",
    "ErrorMonitoringMiddleware",
    "MonitoringMiddleware",
    "PerformanceMiddleware",
    "PerformanceMonitoringConfig",
    "PerformanceMonitoringMiddleware",
    "register_error_monitoring_middleware",
    "register_monitoring_middleware",
    "register_performance_monitoring_middleware",
]
