"""Task definitions."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

TaskCallable = Callable[[], Awaitable[Any]]


@dataclass(slots=True)
class Task:
    name: str
    func: TaskCallable
    max_attempts: int = 1
    timeout_seconds: float | None = None


@dataclass(slots=True)
class TaskResult:
    name: str
    success: bool
    attempts: int
    error: str | None = None
