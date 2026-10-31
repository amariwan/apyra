"""Task definitions."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from math import isfinite
from typing import Any

TaskCallable = Callable[[], Awaitable[Any]]


@dataclass(slots=True)
class Task:
    """Async callable configuration with retry count and optional per-attempt timeout."""

    name: str
    func: TaskCallable
    max_attempts: int = 1
    timeout_seconds: float | None = None

    def __post_init__(self) -> None:
        if type(self.max_attempts) is not int or self.max_attempts < 1:
            raise ValueError("max_attempts must be a positive integer")
        if self.timeout_seconds is not None and (
            isinstance(self.timeout_seconds, bool)
            or not isfinite(self.timeout_seconds)
            or self.timeout_seconds <= 0
        ):
            raise ValueError("timeout_seconds must be finite and greater than zero")


@dataclass(slots=True)
class TaskResult:
    """Outcome of one runner execution, including attempts and final error text."""

    name: str
    success: bool
    attempts: int
    error: str | None = None
