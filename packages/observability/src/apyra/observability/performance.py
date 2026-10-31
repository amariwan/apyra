"""Performance monitoring primitives for Apyra."""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Self


@dataclass(frozen=True)
class PerformanceRecord:
    """A recorded duration measurement."""

    name: str
    duration_seconds: float
    timestamp: float = field(default_factory=time.time)
    tags: dict[str, str] = field(default_factory=lambda: dict[str, str]())


@dataclass(frozen=True)
class PerformanceStats:
    """Aggregated statistics for a named operation."""

    name: str
    count: int
    total_seconds: float
    min_seconds: float
    max_seconds: float
    average_seconds: float


class PerformanceMonitor:
    """Collect and aggregate operation durations."""

    def __init__(self, *, max_records: int = 10000) -> None:
        if max_records <= 0:
            raise ValueError("max_records must be positive")
        self._max_records = max_records
        self._records: defaultdict[str, deque[float]] = defaultdict(
            lambda: deque(maxlen=max_records)
        )
        self._lock = threading.Lock()

    def record(
        self, name: str, duration_seconds: float, *, tags: Mapping[str, str] | None = None
    ) -> PerformanceRecord:
        """Record a duration for a named operation."""
        if duration_seconds < 0:
            raise ValueError("duration_seconds must be non-negative")
        record = PerformanceRecord(
            name=name, duration_seconds=duration_seconds, tags=dict(tags or {})
        )
        with self._lock:
            self._records[name].append(duration_seconds)
        return record

    def record_duration(
        self, name: str, duration_seconds: float, *, tags: Mapping[str, str] | None = None
    ) -> PerformanceRecord:
        """Alias for :meth:`record`."""
        return self.record(name, duration_seconds, tags=tags)

    def stats(self, name: str | None = None) -> dict[str, PerformanceStats]:
        """Return aggregated statistics, optionally for one operation."""
        result: dict[str, PerformanceStats] = {}
        with self._lock:
            if name is not None:
                names = [name] if name in self._records else []
            else:
                names = list(self._records)
            for current in names:
                values = list(self._records[current])
                if not values:
                    continue
                result[current] = PerformanceStats(
                    name=current,
                    count=len(values),
                    total_seconds=sum(values),
                    min_seconds=min(values),
                    max_seconds=max(values),
                    average_seconds=sum(values) / len(values),
                )
        return result

    def snapshot(self) -> dict[str, PerformanceStats]:
        """Return a copy of all aggregated statistics."""
        return self.stats()

    def reset(self, name: str | None = None) -> None:
        """Clear recorded durations."""
        with self._lock:
            if name is None:
                self._records.clear()
            else:
                self._records.pop(name, None)

    @contextmanager
    def measure(self, name: str, *, tags: Mapping[str, str] | None = None) -> Any:
        """Synchronously measure the duration of a block."""
        started_at = time.perf_counter()
        try:
            yield
        finally:
            self.record(name, time.perf_counter() - started_at, tags=tags)

    def timed(
        self, name: str | None = None, *, tags: Mapping[str, str] | None = None
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Decorator measuring sync or async callables."""
        import inspect

        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            operation = name or f"{func.__module__}.{func.__qualname__}"

            if inspect.iscoroutinefunction(func):

                async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                    started_at = time.perf_counter()
                    try:
                        return await func(*args, **kwargs)
                    finally:
                        self.record(operation, time.perf_counter() - started_at, tags=tags)

                return async_wrapper

            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                started_at = time.perf_counter()
                try:
                    return func(*args, **kwargs)
                finally:
                    self.record(operation, time.perf_counter() - started_at, tags=tags)

            return sync_wrapper

        return decorator

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None


class PerformanceTimer:
    """Simple manual timer."""

    def __init__(self, monitor: PerformanceMonitor | None = None, name: str | None = None) -> None:
        self._monitor = monitor
        self._name = name
        self._started_at: float | None = None

    def start(self) -> PerformanceTimer:
        self._started_at = time.perf_counter()
        return self

    def stop(self) -> float:
        if self._started_at is None:
            raise RuntimeError("timer has not been started")
        elapsed = time.perf_counter() - self._started_at
        self._started_at = None
        if self._monitor is not None and self._name is not None:
            self._monitor.record(self._name, elapsed)
        return elapsed

    def __enter__(self) -> Self:
        self.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self.stop()

    async def __aenter__(self) -> Self:
        self.start()
        return self

    async def __aexit__(self, *exc: object) -> None:
        self.stop()


_default_monitor = PerformanceMonitor()
_monitor_lock = threading.Lock()


def get_performance_monitor() -> PerformanceMonitor:
    return _default_monitor


def set_performance_monitor(monitor: PerformanceMonitor) -> None:
    global _default_monitor
    with _monitor_lock:
        _default_monitor = monitor


def record_duration(
    name: str,
    duration_seconds: float,
    *,
    tags: Mapping[str, str] | None = None,
    monitor: PerformanceMonitor | None = None,
) -> PerformanceRecord:
    target = monitor or get_performance_monitor()
    return target.record(name, duration_seconds, tags=tags)


def measure(
    name: str, *, tags: Mapping[str, str] | None = None, monitor: PerformanceMonitor | None = None
) -> Any:
    """Return a context manager measuring a block using the default or supplied monitor."""
    target = monitor or get_performance_monitor()
    return target.measure(name, tags=tags)


@contextmanager
def time_operation(
    name: str, *, tags: Mapping[str, str] | None = None, monitor: PerformanceMonitor | None = None
) -> Any:
    target = monitor or get_performance_monitor()
    with target.measure(name, tags=tags):
        yield


# Aliases for naming flexibility.
PerformanceMeasurement = PerformanceRecord
TimingMonitor = PerformanceMonitor
record_timing = record_duration
record_metric = record_duration
measure_performance = measure
__all__ = [
    "PerformanceMonitor",
    "PerformanceRecord",
    "PerformanceStats",
    "PerformanceTimer",
    "get_performance_monitor",
    "measure",
    "record_duration",
    "set_performance_monitor",
    "time_operation",
]
