"""Error monitoring primitives for Apyra."""

from __future__ import annotations

import functools
import threading
import time
import traceback
from collections import deque
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol, Self

from .logging import get_request_id


@dataclass(frozen=True)
class ErrorEvent:
    """A captured error or exception."""

    event_id: str
    exception_type: str
    message: str
    level: str = "error"
    timestamp: float = field(default_factory=time.time)
    traceback: str | None = None
    request_id: str | None = None
    tags: dict[str, str] = field(default_factory=lambda: dict[str, str]())
    context: dict[str, Any] = field(default_factory=lambda: dict[str, Any]())


class ErrorReporter(Protocol):
    """Contract for an error monitoring backend."""

    def capture_exception(
        self,
        exc: BaseException,
        *,
        level: str = "error",
        tags: Mapping[str, str] | None = None,
        context: Mapping[str, Any] | None = None,
        request_id: str | None = None,
    ) -> str:
        """Capture an exception and return its event identifier."""
        ...

    def capture_message(
        self,
        message: str,
        *,
        level: str = "error",
        tags: Mapping[str, str] | None = None,
        context: Mapping[str, Any] | None = None,
        request_id: str | None = None,
    ) -> str:
        """Capture a message and return its event identifier."""
        ...


class InMemoryErrorReporter:
    """A bounded in-memory error reporter useful for tests and local development."""

    def __init__(self, *, max_events: int = 1000) -> None:
        if max_events <= 0:
            raise ValueError("max_events must be positive")
        self._max_events = max_events
        self._events: deque[ErrorEvent] = deque(maxlen=max_events)
        self._lock = threading.Lock()
        self._counter = 0

    def capture_exception(
        self,
        exc: BaseException,
        *,
        level: str = "error",
        tags: Mapping[str, str] | None = None,
        context: Mapping[str, Any] | None = None,
        request_id: str | None = None,
    ) -> str:
        event_id = self._next_id()
        event = ErrorEvent(
            event_id=event_id,
            exception_type=type(exc).__qualname__,
            message=str(exc),
            level=level,
            traceback="".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
            request_id=request_id if request_id is not None else get_request_id(),
            tags=dict(tags or {}),
            context=dict(context or {}),
        )
        with self._lock:
            self._events.append(event)
        return event_id

    def capture_message(
        self,
        message: str,
        *,
        level: str = "error",
        tags: Mapping[str, str] | None = None,
        context: Mapping[str, Any] | None = None,
        request_id: str | None = None,
    ) -> str:
        event_id = self._next_id()
        event = ErrorEvent(
            event_id=event_id,
            exception_type="Message",
            message=message,
            level=level,
            request_id=request_id if request_id is not None else get_request_id(),
            tags=dict(tags or {}),
            context=dict(context or {}),
        )
        with self._lock:
            self._events.append(event)
        return event_id

    def events(self) -> list[ErrorEvent]:
        with self._lock:
            return list(self._events)

    def clear(self) -> None:
        with self._lock:
            self._events.clear()

    def _next_id(self) -> str:
        with self._lock:
            self._counter += 1
            return f"err-{self._counter}"


_default_reporter: ErrorReporter = InMemoryErrorReporter()
_reporter_lock = threading.Lock()


def get_error_reporter() -> ErrorReporter:
    """Return the process-wide default error reporter."""
    return _default_reporter


def set_error_reporter(reporter: ErrorReporter) -> None:
    """Replace the process-wide default error reporter."""
    global _default_reporter
    with _reporter_lock:
        _default_reporter = reporter


def capture_exception(
    exc: BaseException,
    *,
    level: str = "error",
    tags: Mapping[str, str] | None = None,
    context: Mapping[str, Any] | None = None,
    request_id: str | None = None,
    reporter: ErrorReporter | None = None,
) -> str:
    """Capture an exception using the default or supplied reporter."""
    target = reporter or get_error_reporter()
    return target.capture_exception(
        exc, level=level, tags=tags, context=context, request_id=request_id
    )


def capture_message(
    message: str,
    *,
    level: str = "error",
    tags: Mapping[str, str] | None = None,
    context: Mapping[str, Any] | None = None,
    request_id: str | None = None,
    reporter: ErrorReporter | None = None,
) -> str:
    """Capture a message using the default or supplied reporter."""
    target = reporter or get_error_reporter()
    return target.capture_message(
        message, level=level, tags=tags, context=context, request_id=request_id
    )


class ErrorMonitoringContext:
    """Context manager that captures exceptions and optionally re-raises them."""

    def __init__(
        self,
        *,
        reraise: bool = True,
        level: str = "error",
        tags: Mapping[str, str] | None = None,
        context: Mapping[str, Any] | None = None,
    ) -> None:
        self._reraise = reraise
        self._level = level
        self._tags = tags
        self._context = context

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback_obj: object,
    ) -> bool:
        if exc is not None:
            capture_exception(exc, level=self._level, tags=self._tags, context=self._context)
        return not self._reraise and exc is not None

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback_obj: object,
    ) -> bool:
        return self.__exit__(exc_type, exc, traceback_obj)


def monitor_errors(
    *,
    reraise: bool = True,
    level: str = "error",
    tags: Mapping[str, str] | None = None,
    context: Mapping[str, Any] | None = None,
) -> ErrorMonitoringContext:
    """Return a context manager that captures exceptions raised inside it."""
    return ErrorMonitoringContext(reraise=reraise, level=level, tags=tags, context=context)


def error_monitor(func: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator that captures exceptions raised by a function and re-raises them."""

    import inspect

    if inspect.iscoroutinefunction(func):

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return await func(*args, **kwargs)
            except Exception as exc:
                capture_exception(exc)
                raise

        return async_wrapper

    @functools.wraps(func)
    def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except Exception as exc:
            capture_exception(exc)
            raise

    return sync_wrapper


# Aliases for naming flexibility.
ErrorMonitor = InMemoryErrorReporter
monitor_exception = capture_exception
report_exception = capture_exception
report_error = capture_message
__all__ = [
    "ErrorEvent",
    "ErrorMonitoringContext",
    "ErrorReporter",
    "InMemoryErrorReporter",
    "capture_exception",
    "capture_message",
    "error_monitor",
    "get_error_reporter",
    "monitor_errors",
    "set_error_reporter",
]
